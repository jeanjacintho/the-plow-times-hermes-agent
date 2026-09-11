"""register_crons.py -- the spec derivation and the refusals with teeth."""
from __future__ import annotations

import json
import pathlib

import pytest

from conftest import load_module

crons = load_module("pt_crons", "pt-dashboard/scripts/register_crons.py")

TZ = "America/Los_Angeles"
CONFIG = {
    "owner": {"timezone": TZ},
    "delivery": {"hour": "07:00"},
    "printer": {"configured": False, "name": None},
}


def topic(tid, kind="subscription", status="pending", depth="deep", run_on=None):
    return {"id": tid, "text": f"topic {tid}", "kind": kind, "depth": depth,
            "status": status, "created_at": "now", "last_edition_at": None,
            "scheduled_for": None, "run_on": run_on}


def write_config(tmp_path, config=CONFIG):
    path = tmp_path / "pt" / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config))
    return path


def write_jobs(tmp_path, jobs):
    path = tmp_path / "jobs.json"
    if jobs is None:
        return path  # absent: the only empty-schedule answer
    path.write_text(json.dumps({"jobs": jobs}))
    return path


def job(name, enabled=True, paused_at=None):
    return {"name": name, "enabled": enabled, "paused_at": paused_at}


class TestRegisteredJobs:
    def test_missing_file_is_the_only_empty_answer(self, tmp_path):
        assert crons.registered_jobs(tmp_path / "jobs.json") == {}

    def test_garbage_aborts(self, tmp_path):
        with pytest.raises(Exception):
            crons.registered_jobs(write_jobs(tmp_path, "garbage"))

    def test_wrong_shape_aborts(self, tmp_path):
        path = tmp_path / "jobs.json"
        path.write_text(json.dumps({"nope": []}))
        with pytest.raises(Exception):
            crons.registered_jobs(path)

    def test_paused_is_registered_but_not_runnable(self, tmp_path):
        registered = crons.registered_jobs(write_jobs(tmp_path, [
            job("pt-subscription-t_9f2a"),
            job("pt-subscription-t_0c11", enabled=False),
            job("pt-subscription-t_dead", paused_at="2026-09-09"),
        ]))
        assert registered == {
            "pt-subscription-t_9f2a": True,
            "pt-subscription-t_0c11": False,
            "pt-subscription-t_dead": False,
        }


class TestTimezoneAgreement:
    def test_empty_tz_refuses(self, tmp_path):
        path = write_config(tmp_path)
        with pytest.raises(SystemExit, match="TZ is empty"):
            crons.require_timezone_agreement(path, env={})

    def test_mismatch_refuses_naming_both(self, tmp_path):
        path = write_config(tmp_path)
        with pytest.raises(SystemExit, match="America/Los_Angeles.*America/Chicago"):
            crons.require_timezone_agreement(path, env={"TZ": "America/Chicago"})

    def test_missing_config_refuses(self, tmp_path):
        with pytest.raises(SystemExit, match="missing"):
            crons.require_timezone_agreement(tmp_path / "nope.json", env={"TZ": TZ})

    def test_agreement_passes(self, tmp_path):
        path = write_config(tmp_path)
        crons.require_timezone_agreement(path, env={"TZ": TZ})


class TestResolveDeliver:
    def test_expands(self):
        env = {"PLOW_HOME_CHANNEL": "chat_123"}
        assert crons.resolve_deliver("plow_chat:${PLOW_HOME_CHANNEL}", env) == \
            "plow_chat:chat_123"

    def test_blank_refuses_by_name(self):
        with pytest.raises(SystemExit, match="PLOW_HOME_CHANNEL"):
            crons.resolve_deliver("plow_chat:${PLOW_HOME_CHANNEL}", {})


class TestDesiredJobs:
    def test_one_job_per_active_subscription(self, tmp_path):
        path = write_config(tmp_path)
        topics = [topic("t_9f2a"), topic("t_0c11")]
        jobs = crons.desired_jobs(topics, "07:00", {"PLOW_HOME_CHANNEL": "c"})
        assert [j["name"] for j in jobs] == [
            "pt-subscription-t_9f2a", "pt-subscription-t_0c11"]
        assert all(j["schedule"] == "0 7 * * *" for j in jobs)
        assert all(j["deliver"] == crons.DELIVER_TARGET for j in jobs)
        assert path.name == "config.json"  # config untouched

    def test_cancelled_subscription_gets_no_job(self):
        jobs = crons.desired_jobs(
            [topic("t_9f2a", status="cancelled")], "07:00", {})
        assert jobs == []

    def test_one_offs_never_get_subscription_jobs(self):
        jobs = crons.desired_jobs(
            [topic("t_0c11", kind="one_off", status="pending", depth="quick")],
            "07:00", {})
        assert jobs == []

    def test_running_subscription_still_has_its_job(self):
        jobs = crons.desired_jobs([topic("t_9f2a", status="running")], "07:00", {})
        assert len(jobs) == 1

    def test_hour_derived_without_leading_zero(self):
        jobs = crons.desired_jobs([topic("t_9f2a")], "23:00", {})
        assert jobs[0]["schedule"] == "0 23 * * *"


class TestStaleNames:
    def test_cancelled_subscription_pruned(self):
        stale = crons.stale_names(
            [topic("t_9f2a", status="cancelled")],
            {"pt-subscription-t_9f2a": True},
        )
        assert stale == ["pt-subscription-t_9f2a"]

    def test_delivered_oneoff_pruned(self):
        stale = crons.stale_names(
            [topic("t_0c11", kind="one_off", status="delivered", depth="quick")],
            {"pt-oneoff-t_0c11": True},
        )
        assert stale == ["pt-oneoff-t_0c11"]

    def test_pending_oneoff_kept(self):
        stale = crons.stale_names(
            [topic("t_0c11", kind="one_off", status="pending", depth="quick")],
            {"pt-oneoff-t_0c11": True},
        )
        assert stale == []

    def test_job_with_no_topic_pruned(self):
        assert crons.stale_names([], {"pt-subscription-t_ffff": True}) == \
            ["pt-subscription-t_ffff"]

    def test_foreign_names_never_touched(self):
        registered = {"ld-weather": True, "pt-subscription-notanid": True,
                      "pt-subscription-t_9f2a-extra": True}
        assert crons.stale_names([topic("t_9f2a")], registered) == []


class TestCreateArgv:
    def test_argv_shape(self):
        jobs = crons.desired_jobs([topic("t_9f2a")], "07:00",
                                  {"PLOW_HOME_CHANNEL": "chat_123"})
        argv = crons.create_argv(jobs[0], {"PLOW_HOME_CHANNEL": "chat_123"})
        assert argv[0:5] == [crons.HERMES, "cron", "create", "0 7 * * *",
                             argv[4]]
        assert "--name" in argv and "pt-subscription-t_9f2a" in argv
        assert "--deliver" in argv and "plow_chat:chat_123" in argv
        assert argv[argv.index("--deliver") + 1] == "plow_chat:chat_123"


class TestMain:
    @pytest.fixture
    def hermes(self, tmp_path, monkeypatch):
        fake = tmp_path / "hermes"
        fake.write_text("#!/bin/sh\nexit 0\n")
        fake.chmod(0o755)
        monkeypatch.setattr(crons, "HERMES", str(fake))
        return fake

    def run_main(self, tmp_path, monkeypatch, topics_list, registered,
                 calls=None, runner=None, env=None):
        pt_home = tmp_path / "pt"
        pt_home.mkdir(exist_ok=True)
        (pt_home / "config.json").write_text(json.dumps(CONFIG))
        (pt_home / "topics.json").write_text(json.dumps({"topics": topics_list}))
        jobs_path = write_jobs(tmp_path, registered)
        monkeypatch.setenv("PT_HOME", str(pt_home))
        monkeypatch.chdir(tmp_path)

        if runner is None:
            def runner(argv):
                if calls is not None:
                    calls.append(argv)
                return type("P", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        return crons.main(
            jobs_path=jobs_path,
            config_path=pt_home / "config.json",
            env=env if env is not None else {"TZ": TZ, "PLOW_HOME_CHANNEL": "chat_123"},
            runner=runner,
        )

    def test_registers_missing_subscription(
            self, tmp_path, monkeypatch, hermes):
        calls = []
        code = self.run_main(tmp_path, monkeypatch,
                             [topic("t_9f2a")], [], calls=calls)
        assert code == 0
        assert any("create" in " ".join(c) for c in calls)

    def test_idempotent_run_skips_present(self, tmp_path, monkeypatch, hermes):
        calls = []
        code = self.run_main(tmp_path, monkeypatch, [topic("t_9f2a")],
                             [job("pt-subscription-t_9f2a")], calls=calls)
        assert code == 0
        assert calls == []  # nothing created, nothing removed

    def test_removes_stale_and_creates_missing(
            self, tmp_path, monkeypatch, hermes):
        calls = []
        code = self.run_main(
            tmp_path, monkeypatch,
            [topic("t_0c11")],  # t_0c11 active; t_ffff job orphaned
            [job("pt-subscription-t_ffff")], calls=calls)
        assert code == 0
        assert any("remove" in c and "pt-subscription-t_ffff" in c for c in calls)
        assert any("create" in " ".join(c) and "pt-subscription-t_0c11" in " ".join(c)
                   for c in calls)

    def test_failed_create_lears_loud(self, tmp_path, monkeypatch, hermes):
        def failing(argv):
            return type("P", (), {"returncode": 1, "stdout": "boom",
                                  "stderr": "bad schedule"})()
        with pytest.raises(SystemExit, match="could not register"):
            self.run_main(tmp_path, monkeypatch, [topic("t_9f2a")], [],
                          runner=failing)

    def test_blank_home_channel_refuses(self, tmp_path, monkeypatch, hermes):
        with pytest.raises(SystemExit, match="PLOW_HOME_CHANNEL"):
            self.run_main(tmp_path, monkeypatch, [topic("t_9f2a")], [],
                          env={"TZ": TZ})


class TestDailySchedule:
    def test_plain_lead(self):
        assert crons.daily_schedule("07:00", 45) == "15 6 * * *"

    def test_zero_lead_is_the_hour(self):
        assert crons.daily_schedule("07:00", 0) == "0 7 * * *"

    def test_midnight_wraps_to_previous_day(self):
        # 00:00 - 45min is 23:15 the day before -- a valid daily expression,
        # not "45 -1 * * *".
        assert crons.daily_schedule("00:00", 45) == "15 23 * * *"

    def test_lead_over_the_hour_wraps(self):
        # 00:00 - 90min is 22:30 the day before.
        assert crons.daily_schedule("00:00", 90) == "30 22 * * *"


class TestHasPaper:
    def test_section_keeps_the_paper(self):
        assert crons.has_paper([topic("t_1", kind="section", status="pending")])

    def test_delivered_section_still_counts(self):
        assert crons.has_paper([topic("t_1", kind="section", status="delivered")])

    def test_cancelled_section_does_not(self):
        assert not crons.has_paper([topic("t_1", kind="section", status="cancelled")])

    def test_pending_assignment_keeps_the_paper(self):
        assert crons.has_paper([topic("t_1", kind="assignment", status="pending",
                                      run_on="2026-09-11")])

    def test_running_assignment_keeps_the_paper(self):
        assert crons.has_paper([topic("t_1", kind="assignment", status="running",
                                      run_on="2026-09-11")])

    def test_delivered_assignment_does_not(self):
        assert not crons.has_paper([topic("t_1", kind="assignment", status="delivered",
                                          run_on="2026-09-11")])

    def test_subscription_alone_has_no_paper(self):
        assert not crons.has_paper([topic("t_1")])


class TestDailyJob:
    def test_included_when_a_section_exists(self):
        jobs = crons.desired_jobs(
            [topic("t_1", kind="section", status="pending")], "07:00", {}, 45)
        assert jobs[0]["name"] == crons.DAILY_NAME
        assert jobs[0]["schedule"] == "15 6 * * *"
        assert jobs[0]["deliver"] == crons.DELIVER_TARGET
        assert jobs[0]["skill"] == "pt-research"

    def test_included_when_an_assignment_is_due(self):
        jobs = crons.desired_jobs(
            [topic("t_1", kind="assignment", status="pending", run_on="2026-09-11")],
            "07:00", {}, 45)
        assert [j["name"] for j in jobs] == [crons.DAILY_NAME]

    def test_absent_without_paper(self):
        jobs = crons.desired_jobs([topic("t_9f2a")], "07:00", {}, 45)
        assert [j["name"] for j in jobs] == ["pt-subscription-t_9f2a"]

    def test_daily_precedes_subscriptions(self):
        jobs = crons.desired_jobs(
            [topic("t_1", kind="section"), topic("t_9f2a")], "07:00", {}, 45)
        assert [j["name"] for j in jobs] == [
            crons.DAILY_NAME, "pt-subscription-t_9f2a"]


class TestDailyStale:
    def test_daily_pruned_when_no_paper_left(self):
        assert crons.stale_names([], {crons.DAILY_NAME: True}) == [crons.DAILY_NAME]

    def test_daily_kept_while_a_section_lives(self):
        stale = crons.stale_names(
            [topic("t_1", kind="section")], {crons.DAILY_NAME: True})
        assert stale == []

    def test_daily_kept_while_an_assignment_runs(self):
        stale = crons.stale_names(
            [topic("t_1", kind="assignment", status="running", run_on="2026-09-11")],
            {crons.DAILY_NAME: True})
        assert stale == []


class TestDrift:
    def test_schedule_drift_detected(self):
        job = {"name": "pt-daily-edition", "schedule": "15 6 * * *", "skill": "pt-research"}
        spec = {"schedule": "0 7 * * *", "skill": "pt-research", "deliver": None}
        assert crons.job_drift(job, spec) is True

    def test_absent_schedule_is_not_drift(self):
        job = {"name": "pt-subscription-t_9f2a", "schedule": "0 7 * * *",
               "skill": "pt-research"}
        assert crons.job_drift(job, {}) is False

    def test_matching_spec_is_not_drift(self):
        job = {"name": "pt-daily-edition", "schedule": "15 6 * * *", "skill": "pt-research"}
        spec = {"schedule": "15 6 * * *", "skill": "pt-research", "deliver": "x"}
        assert crons.job_drift(job, spec) is False

    def test_skill_drift_detected(self):
        job = {"name": "pt-daily-edition", "schedule": "15 6 * * *", "skill": "pt-edition"}
        spec = {"schedule": "15 6 * * *", "skill": "pt-research", "deliver": None}
        assert crons.job_drift(job, spec) is True

    def test_registered_specs_reads_fields(self, tmp_path):
        path = tmp_path / "jobs.json"
        path.write_text(json.dumps({"jobs": [
            {"name": "pt-daily-edition", "schedule": "15 6 * * *",
             "skill": "pt-research", "deliver": "plow_chat:c", "enabled": True,
             "paused_at": None},
        ]}))
        specs = crons.registered_specs(path)
        assert specs["pt-daily-edition"]["schedule"] == "15 6 * * *"


class TestDriftMain:
    @pytest.fixture
    def hermes(self, tmp_path, monkeypatch):
        fake = tmp_path / "hermes"
        fake.write_text("#!/bin/sh\nexit 0\n")
        fake.chmod(0o755)
        monkeypatch.setattr(crons, "HERMES", str(fake))
        return fake

    def run_main(self, tmp_path, monkeypatch, topics_list, registered, runner):
        pt_home = tmp_path / "pt"
        pt_home.mkdir(exist_ok=True)
        (pt_home / "config.json").write_text(json.dumps(CONFIG))
        (pt_home / "topics.json").write_text(json.dumps({"topics": topics_list}))
        jobs_path = write_jobs(tmp_path, registered)
        monkeypatch.setenv("PT_HOME", str(pt_home))
        monkeypatch.chdir(tmp_path)
        return crons.main(
            jobs_path=jobs_path,
            config_path=pt_home / "config.json",
            env={"TZ": TZ, "PLOW_HOME_CHANNEL": "chat_123"},
            runner=runner,
        )

    def test_drifted_job_removed_and_recreated(self, tmp_path, monkeypatch, hermes):
        calls = []
        def runner(argv):
            calls.append(argv)
            return type("P", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        code = self.run_main(
            tmp_path, monkeypatch,
            [topic("t_1", kind="section")],
            [{"name": crons.DAILY_NAME, "enabled": True, "paused_at": None,
              "schedule": "0 7 * * *", "skill": "pt-research"}],
            runner)
        assert code == 0
        assert any("remove" in c for c in calls)
        assert any("create" in " ".join(c) for c in calls)
        assert not any(c == ["already present"] for c in calls)

    def test_stale_daily_removed(self, tmp_path, monkeypatch, hermes):
        calls = []
        def runner(argv):
            calls.append(argv)
            return type("P", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        # A subscription keeps no paper; the daily job is stale.
        self.run_main(
            tmp_path, monkeypatch,
            [topic("t_9f2a")],
            [{"name": crons.DAILY_NAME, "enabled": True, "paused_at": None}],
            runner)
        assert any("remove" in c and crons.DAILY_NAME in c for c in calls)


class TestPrune:
    def test_old_lock_pruned_today_kept(self, tmp_path):
        run = tmp_path / "run"
        run.mkdir()
        old = run / "daily-2020-01-01.lock"
        old.write_text("x")
        from datetime import date
        today = run / f"daily-{date.today().isoformat()}.lock"
        today.write_text("x")
        removed = crons.prune_runtime([], tmp_path)
        assert str(old) in removed
        assert not old.exists()
        assert today.exists()

    def test_terminal_topic_notes_pruned(self, tmp_path):
        run = tmp_path / "run"
        (run / "t_dead").mkdir(parents=True)
        (run / "t_live").mkdir()
        topics = [topic("t_dead", kind="assignment", status="delivered",
                        run_on="2026-09-11"),
                  topic("t_live", kind="section", status="pending")]
        removed = crons.prune_runtime(topics, tmp_path)
        assert str(run / "t_dead") in removed
        assert not (run / "t_dead").exists()
        assert (run / "t_live").exists()