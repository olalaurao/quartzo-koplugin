"""Adversarial report envelopes only; native state proof is a separate test."""
import copy
from pathlib import Path
import unittest
from unittest import mock

import outbox_probe_bundle as bundle


class SourceProbeEnvelopeTest(unittest.TestCase):
    def inputs(self):
        manifest=dict(run_id="a"*32,source_commit="b"*40,files={"probe.lua":"c"*64})
        expected=dict(native_source_sha256={name:"d"*64 for name in bundle.NATIVE})
        device=dict(probe_version=1,probe_kind="source_lifecycle",phase="passed",source_data="synthetic",
            uses_synthetic_clock=True,user_statistics_accessed=False,synthetic_statistics_accessed=True,
            network_accessed=False,wifi_changed=False,canonical_ack=False,ack_watermark_changed=False,
            source_epoch_verified=False,gate4_passed=False,case_checks=dict.fromkeys(bundle.SOURCE_CASES,True),
            process_stop_cases=2,same_second_events=251,recovery_identity_retained=True,
            legacy_upgrade_preserved=True,nonempty_generation_refused=True,run_id=manifest["run_id"],
            manifest_digest="e"*64,source_commit=manifest["source_commit"],lua_version="Lua 5.1",
            jit_arch="arm",koreader_version=bundle.base.BASELINE,native_source_sha256=expected["native_source_sha256"],
            jit_version="LuaJIT 2.1.0-beta3",json_version="dkjson 2.10",cpu_seconds=0.1)
        return manifest,"e"*64,expected,device,Path("synthetic-model-target")

    def test_verified_envelope_still_requires_independent_state_and_cannot_attest_hardware(self):
        with mock.patch.object(bundle.base,"collection_inputs",return_value=self.inputs()) as inputs, \
                mock.patch.object(bundle,"inspect_source_state",return_value={"fixture":"f"*64}) as state:
            report=bundle.collect_source("bundle","mount","observation")
            self.assertEqual(inputs.call_args.args[-1],bundle.SOURCE_DEFINITION)
            state.assert_called_once_with(Path("synthetic-model-target/state"))
            self.assertTrue(report["observations_match"])
            for name in ("physical_execution_attested","canonical_ack","source_epoch_verified","gate4_passed","production_changed"):
                self.assertIs(report[name],False)
        with mock.patch.object(bundle.base,"collection_inputs",return_value=self.inputs()), \
                mock.patch.object(bundle,"inspect_source_state",side_effect=ValueError("synthetic mismatch")):
            with self.assertRaises(ValueError): bundle.collect_source("bundle","mount","observation")

    def test_old_reports_extra_claims_boolean_numbers_and_partial_cases_fail_before_state(self):
        mutations=[("probe_kind","old_offline_probe"),("gate4_passed",True),("canonical_ack",True),
            ("user_statistics_accessed",True),("process_stop_cases",True),("cpu_seconds",float("nan")),
            ("same_second_events",250),("case_checks",dict.fromkeys(bundle.SOURCE_CASES,1)),
            ("case_checks",{"collection_after_commit":True}),("unexpected_claim",True)]
        for key,value in mutations:
            with self.subTest(key=key,value=value):
                args=list(copy.deepcopy(self.inputs()))
                args[3][key]=value
                with mock.patch.object(bundle.base,"collection_inputs",return_value=tuple(args)), \
                        mock.patch.object(bundle,"inspect_source_state") as state:
                    with self.assertRaises(ValueError): bundle.collect_source("bundle","mount","observation")
                    state.assert_not_called()


if __name__=="__main__": unittest.main()
