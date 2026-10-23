"""Finite synthetic offline outbox proof; reuse the existing single-use artifact owner."""
import calendar
import json
from pathlib import Path
import re
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reading_wire"))
import probe_bundle as base

NAME = "quartzo-outbox-probe"
SOURCES = {"outbox.lua":"quartzo.koplugin/quartzo/outbox.lua",
    "paired_exchange.lua":"quartzo.koplugin/quartzo/paired_exchange.lua",
    "codec.lua":"quartzo.koplugin/quartzo/codec.lua", "koreader_deps.lua":"quartzo.koplugin/quartzo/koreader_deps.lua",
    "probe.lua":"tools/plugin/outbox_probe.lua", "kindle.lua":"tools/plugin/outbox_probe_kindle.lua",
    "run.sh":"tools/transport_probe/run.sh", "menu.json":"tools/plugin/outbox_probe_menu.json",
    "config.xml":"tools/plugin/outbox_probe_config.xml"}
NATIVE = {"dkjson":"common/dkjson.lua", "sha2":"ffi/sha2.lua",
    "sqlite_wrapper":"common/lua-ljsqlite3/init.lua", "posix":"ffi/posix_h.lua",
    "sqlite":"libs/libsqlite3.so.0", "filesystem":"libs/libkoreader-lfs.so", "luajit":"luajit"}
DEFINITION = base.ProbeDefinition(NAME,SOURCES,NATIVE,frozenset({"state"}))
CASES = {f"{operation}_{position}_commit" for operation in ("stage","backup","restore")
         for position in ("before","after")}
FALSE_FIELDS = ("statistics_accessed","network_accessed","wifi_changed","source_cursor_changed",
                "canonical_ack","canonical_persistence_proven","paired_receipt_proven",
                "source_epoch_verified","gate4_passed")
PRIMARY = "quartzo_sync_state.sqlite3"
PRESERVED = "quartzo_sync_state_preserved.sqlite3"
COLUMNS = {
    "identity": [("id","INTEGER",0,1),("device_id","TEXT",1,0),("source_epoch","TEXT",1,0)],
    "pending": [("event_id","TEXT",0,1),("line","TEXT",1,0),("native_digest","TEXT",1,0)],
    "review": [("started_at","INTEGER",1,1),("book_id","TEXT",1,2),("page","TEXT",1,3),
               ("duration","TEXT",1,4),("pages","TEXT",1,5),("types","TEXT",1,6)]}


def require(value):
    if not value:
        raise ValueError("Offline outbox observation mismatch")


def compact(value):
    return json.dumps(value,separators=(",", ":"),ensure_ascii=False)


def fixture_rows(device,epoch):
    """Independent test-only contract reconstruction, never production serialization."""
    rows=[]
    for index in range(2):
        started=f"2026-10-14T02:50:0{index}.000Z"
        seconds=calendar.timegm((2026,10,14,2,50,index))
        preimage=["quartzo-reading-event-v1",device,epoch,17,4+index,seconds]
        event_id="qre_"+base.sha(compact(preimage).encode())
        event=dict(schema_version=1,event_id=event_id,source="koreader_statistics",device_id=device,
            source_epoch=epoch,book_row_id=17,page=4+index,started_at_utc=started,
            duration_seconds=20 if index==0 else 30,total_pages=120,
            observed_at_utc="2026-10-16T12:00:00.000Z",source_schema_version="fixture_only")
        native={key:value for key,value in event.items() if key!="observed_at_utc"}
        rows.append((event_id,compact(event),base.sha(compact(native).encode())))
    return sorted(rows)


def inspect_copy(path,partial,pending,epoch):
    # This connection is only to a bounded PRIVATE COPY of synthetic diagnostic
    # state. Never open a mounted user/Statistics DB, even in SQLite ro mode.
    connection=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)
    try:
        require(connection.execute("PRAGMA quick_check(1)").fetchone()==("ok",))
        version=connection.execute("PRAGMA user_version").fetchone()[0]
        objects=connection.execute("SELECT name,type FROM sqlite_master WHERE name NOT GLOB 'sqlite_*' LIMIT 4").fetchall()
        if partial:
            require(version==0 and objects==[])
            return None
        require(version==1 and set(objects)=={(name,"table") for name in COLUMNS})
        for name,expected in COLUMNS.items():
            columns=connection.execute("PRAGMA table_info("+name+")").fetchall()
            require(len(columns)==len(expected))
            require(all(row==(index,column,kind,nonnull,None,pk)
                for index,(row,(column,kind,nonnull,pk)) in enumerate(zip(columns,expected))))
        identities=connection.execute("SELECT id,device_id,source_epoch FROM identity LIMIT 2").fetchall()
        require(len(identities)==1)
        number,device,source=identities[0]
        require(number==1 and isinstance(device,str) and re.fullmatch(r"qrd_[a-f0-9]{32}",device) and source==epoch)
        actual=connection.execute("SELECT event_id,line,native_digest FROM pending ORDER BY event_id LIMIT 3").fetchall()
        require(actual==(fixture_rows(device,source) if pending else []))
        review=connection.execute("SELECT started_at,book_id,page,duration,pages,types FROM review LIMIT 2").fetchall()
        require(review==([(1791946202,"17","0","10","120","integer,integer,integer,integer,integer")] if pending else []))
        return device
    finally:
        connection.close()


def inspect_state(state,run_id):
    base.plain_root(state)
    require({entry.name for entry in state.iterdir()}==CASES)
    hashes,ids={},set()
    total=0
    with tempfile.TemporaryDirectory(prefix="quartzo-outbox-private-collection-") as temporary:
        for name in sorted(CASES):
            directory=state/name
            base.plain_root(directory)
            require(directory.is_dir())
            entries={entry.name for entry in directory.iterdir()}
            expected={PRIMARY,"gate.ready"}
            backup=None
            if name.startswith(("backup_","restore_")):
                backups=[leaf for leaf in entries if re.fullmatch(r"quartzo_sync_recovery_[a-f0-9]{32}\.sqlite3",leaf)]
                require(len(backups)==1)
                backup=backups[0]
                expected.add(backup)
            if name.startswith("restore_"):
                expected.add(PRESERVED)
            require(entries==expected)
            require(base.read(directory/"gate.ready",16)==b"ready")
            contexts=set()
            for leaf in sorted(expected-{"gate.ready"}):
                partial=(name=="restore_before_commit" and leaf==PRIMARY
                         or name=="backup_before_commit" and leaf==backup)
                data=base.read(directory/leaf,2097152)
                # Native hot-journal rollback can truncate a newly created
                # destination to zero. It is still an UNREGISTERED partial,
                # never a healthy empty outbox. No other file may be empty.
                require(partial or len(data)>0)
                total+=len(data)
                require(total<=4194304)
                private=Path(temporary)/(name+"-"+leaf)
                with private.open("xb") as stream:
                    stream.write(data)
                context=inspect_copy(private,partial,name!="stage_before_commit","probe_"+run_id)
                if context is not None:
                    contexts.add(context)
                hashes[name+"/"+leaf]=base.sha(data)
            require(len(contexts)==1 and not contexts&ids)
            ids.update(contexts)
    require(len(ids)==6)
    return hashes


def collect(bundle,root,observation,definition=DEFINITION):
    manifest,digest,expected,device,target=base.collection_inputs(bundle,root,observation,definition)
    required=dict(probe_version=1,phase="passed",source_data="synthetic",uses_synthetic_clock=True,
        case_checks=dict.fromkeys(CASES,True),process_stop_cases=6,raw_receipt_rejections=5,
        native_entropy_cases=6,identity_and_pending_verified=True,run_id=manifest["run_id"],
        manifest_digest=digest,source_commit=manifest["source_commit"],lua_version="Lua 5.1",
        jit_arch="arm",koreader_version=base.BASELINE,native_source_sha256=expected["native_source_sha256"])
    required.update(dict.fromkeys(FALSE_FIELDS,False))
    require(set(device)==set(required)|{"jit_version","json_version","cpu_seconds"})
    for key,value in required.items():
        require(type(device[key]) is type(value) and device[key]==value)
    require(all(value is True for value in device["case_checks"].values()))
    require(isinstance(device["jit_version"],str) and re.fullmatch(r"LuaJIT 2\.1[ A-Za-z0-9.()_-]{0,96}",device["jit_version"]))
    require(isinstance(device["json_version"],str) and re.fullmatch(r"dkjson [0-9]+\.[0-9]+",device["json_version"]))
    require(type(device["cpu_seconds"]) in (int,float) and 0<=device["cpu_seconds"]<120)
    state_hashes=inspect_state(target/"state",manifest["run_id"])
    return dict(probe_version=1,proof="correlated_offline_outbox_observations",source_data="synthetic",
        source_commit=manifest["source_commit"],run_id=manifest["run_id"],observations_match=True,
        physical_execution_attested=False,canonical_ack=False,canonical_persistence_proven=False,
        paired_receipt_proven=False,source_epoch_verified=False,gate4_passed=False,production_changed=False,
        process_stop_cases=6,raw_receipt_rejections=5,source_sha256=manifest["files"],
        native_source_sha256=expected["native_source_sha256"],synthetic_state_sha256=state_hashes)


if __name__=="__main__":
    base.main(DEFINITION,collect)
