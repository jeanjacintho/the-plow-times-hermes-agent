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

    def test_mismatch_no_longer_refuses(self, tmp_path):
        # pt-setup now converts the owner's stated local delivery time into
        # the container's local hour at write time (zoneinfo math), so
        # delivery.hour is trusted as already correct for this container --
        # owner.timezone naming a different real zone than TZ is the normal
        # case now, not a refusal. See the module docstring.
        path = write_config(tmp_path)
        crons.require_timezone_agreement(path, env={"TZ": "America/Chicago"})

    def test_blank_owner_timezone_refuses(self, tmp_path):
        blank_tz_config = {**CONFIG, "owner": {"timezone": ""}}
        path = write_config(tmp_path, config=blank_tz_config)
        with pytest.raises(SystemExit, match="blank owner.timezone"):
            crons.require_timezone_agreement(path, env={"TZ": TZ})

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
            crons.DAILY_NAME,
            "pt-subscription-t_9f2a", "pt-subscription-t_0c11"]
        subs = [j for j in jobs if j["name"].startswith("pt-subscription-")]
        assert all(j["schedule"] == "0 7 * * *" for j in subs)
        assert all(j["deliver"] == crons.DELIVER_TARGET for j in jobs)
        assert path.name == "config.json"  # config untouched

    def test_cancelled_subscription_gets_no_job(self):
        jobs = crons.desired_jobs(
            [topic("t_9f2a", status="cancelled")], "07:00", {})
        assert [j["name"] for j in jobs] == [crons.DAILY_NAME]

    def test_one_offs_never_get_subscription_jobs(self):
        jobs = crons.desired_jobs(
            [topic("t_0c11", kind="one_off", status="pending", depth="quick")],
            "07:00", {})
        assert [j["name"] for j in jobs] == [crons.DAILY_NAME]

    def test_running_subscription_still_has_its_job(self):
        jobs = crons.desired_jobs([topic("t_9f2a", status="running")], "07:00", {})
        assert [j["name"] for j in jobs] == [crons.DAILY_NAME, "pt-subscription-t_9f2a"]

    def test_hour_derived_without_leading_zero(self):
        jobs = crons.desired_jobs([topic("t_9f2a")], "23:00", {})
        sub = next(j for j in jobs if j["name"] == "pt-subscription-t_9f2a")
        assert sub["schedule"] == "0 23 * * *"


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
        sub = next(j for j in jobs if j["name"] == "pt-subscription-t_9f2a")
        argv = crons.create_argv(sub, {"PLOW_HOME_CHANNEL": "chat_123"})
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
                             [job(crons.DAILY_NAME), job("pt-subscription-t_9f2a")],
                             calls=calls)
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

    def test_default_lead_is_twenty(self):
        jobs = crons.desired_jobs(
            [topic("t_1", kind="section")], "07:00", {})
        assert jobs[0]["schedule"] == "40 6 * * *"
        assert crons.DEFAULT_LEAD_MINUTES == 20

    def test_zero_lead_is_the_hour(self):
        assert crons.daily_schedule("07:00", 0) == "0 7 * * *"

    def test_midnight_wraps_to_previous_day(self):
        # 00:00 - 45min is 23:15 the day before -- a valid daily expression,
        # not "45 -1 * * *".
        assert crons.daily_schedule("00:00", 45) == "15 23 * * *"

    def test_lead_over_the_hour_wraps(self):
        # 00:00 - 90min is 22:30 the day before.
        assert crons.daily_schedule("00:00", 90) == "30 22 * * *"

    def test_owner_chosen_minute_is_not_forced_to_zero(self):
        # delivery.hour used to be restricted to "HH:00" on the theory that
        # the cron fires at the hour -- it never did; the minute field was
        # always there, only ever fed a computed value.
        assert crons.daily_schedule("10:25", 0) == "25 10 * * *"

    def test_owner_chosen_minute_survives_a_lead_offset(self):
        assert crons.daily_schedule("10:25", 10) == "15 10 * * *"


class TestSubscriptionJob:
    def test_carries_the_owner_chosen_minute(self):
        job = crons.subscription_job(topic("t_9f2a"), "10:25")
        assert job["schedule"] == "25 10 * * *"

    def test_whole_hour_still_works(self):
        job = crons.subscription_job(topic("t_9f2a"), "07:00")
        assert job["schedule"] == "0 7 * * *"


class TestExtraDailyHours:
    # Regression: a user asked for a second daily edition at 10:30 and the
    # model, having no sanctioned way to do that, hand-registered a cron job
    # by shell command instead -- wrong schedule (17 minutes from creation
    # time, not 10:30), a name (pt-daily-edition-2) this script didn't know
    # to manage, and a hand-typed prompt that dropped the --pdf leg. These
    # tests are the real feature that makes the hand-rolled version
    # unnecessary.
    def test_desired_jobs_adds_one_per_extra_hour(self):
        jobs = crons.desired_jobs(
            [topic("t_1", kind="section")], "03:00", {"PLOW_HOME_CHANNEL": "c"},
            45, extra_hours=["10:30"],
        )
        names = [j["name"] for j in jobs]
        assert names == ["pt-daily-edition", "pt-daily-edition-2"]
        # Each slot gets its own lead-time subtraction -- 10:30 minus 45m.
        assert jobs[1]["schedule"] == "45 9 * * *"
        assert jobs[1]["skill"] == "pt-research"
        assert jobs[1]["deliver"] == crons.DELIVER_TARGET

    def test_extra_job_prompt_has_its_own_lock_and_the_pdf_leg(self):
        jobs = crons.desired_jobs(
            [topic("t_1", kind="section")], "03:00", {}, 45, extra_hours=["10:30"],
        )
        prompt = jobs[1]["prompt"]
        assert "daily2-<today's date" in prompt
        assert "post_to_chat.py" in prompt

    def test_no_extra_hours_is_unchanged(self):
        jobs = crons.desired_jobs([topic("t_1", kind="section")], "03:00", {}, 45)
        assert [j["name"] for j in jobs] == ["pt-daily-edition"]

    def test_multiple_extra_hours_are_numbered_in_order(self):
        jobs = crons.desired_jobs(
            [topic("t_1", kind="section")], "03:00", {}, 45,
            extra_hours=["10:30", "16:00"],
        )
        assert [j["name"] for j in jobs] == [
            "pt-daily-edition", "pt-daily-edition-2", "pt-daily-edition-3",
        ]

    def test_stale_extra_job_beyond_configured_count_is_pruned(self):
        stale = crons.stale_names(
            [topic("t_1", kind="section")],
            ["pt-daily-edition", "pt-daily-edition-2", "pt-daily-edition-3"],
            extra_hours_count=1,
        )
        assert stale == ["pt-daily-edition-3"]

    def test_extra_job_kept_when_still_configured(self):
        stale = crons.stale_names(
            [topic("t_1", kind="section")],
            ["pt-daily-edition", "pt-daily-edition-2"],
            extra_hours_count=1,
        )
        assert stale == []

    def test_extra_jobs_kept_when_news_topics_are_gone(self):
        stale = crons.stale_names(
            [], ["pt-daily-edition", "pt-daily-edition-2"], extra_hours_count=1,
        )
        assert stale == []


class TestHasPaper:
    def test_always_true_with_a_section(self):
        assert crons.has_paper([topic("t_1", kind="section", status="pending")])

    def test_always_true_with_no_news_topics(self):
        # Weather and calendar desks still fill a paper.
        assert crons.has_paper([])

    def test_always_true_with_only_a_subscription(self):
        assert crons.has_paper([topic("t_1")])


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

    def test_present_even_without_news_sections(self):
        jobs = crons.desired_jobs([topic("t_9f2a")], "07:00", {}, 45)
        assert [j["name"] for j in jobs] == [crons.DAILY_NAME, "pt-subscription-t_9f2a"]

    def test_daily_precedes_subscriptions(self):
        jobs = crons.desired_jobs(
            [topic("t_1", kind="section"), topic("t_9f2a")], "07:00", {}, 45)
        assert [j["name"] for j in jobs] == [
            crons.DAILY_NAME, "pt-subscription-t_9f2a"]


class TestDailyStale:
    def test_daily_kept_with_no_news_topics(self):
        assert crons.stale_names([], {crons.DAILY_NAME: True}) == []

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

    def test_registered_specs_unwraps_the_real_schedule_shape(self, tmp_path):
        # A real registered job's "schedule" is a dict, not a bare string --
        # {"kind": "cron", "expr": "...", "display": "..."}. Measured against
        # this fleet's own jobs.json, not a guess: comparing that dict
        # straight to a spec's plain string made job_drift() true for every
        # managed job on every run.
        path = tmp_path / "jobs.json"
        path.write_text(json.dumps({"jobs": [
            {"name": "pt-daily-edition",
             "schedule": {"kind": "cron", "expr": "15 2 * * *", "display": "15 2 * * *"},
             "skill": "pt-research", "deliver": "plow_chat:c"},
        ]}))
        specs = crons.registered_specs(path)
        assert specs["pt-daily-edition"]["schedule"] == "15 2 * * *"

    def test_no_drift_against_the_real_schedule_shape(self):
        # The regression this whole helper exists for: an UNCHANGED job,
        # read back in its real persisted shape, must not read as drifted.
        job = {"name": "pt-daily-edition", "schedule": "15 2 * * *", "skill": "pt-research"}
        real_spec = {
            "schedule": crons._persisted_schedule_expr(
                {"schedule": {"kind": "cron", "expr": "15 2 * * *", "display": "15 2 * * *"}}
            ),
            "skill": "pt-research",
            "deliver": "plow_chat:c",
        }
        assert not crons.job_drift(job, real_spec)


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

    def test_daily_kept_while_only_a_subscription_lives(self, tmp_path, monkeypatch, hermes):
        calls = []
        def runner(argv):
            calls.append(argv)
            return type("P", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        self.run_main(
            tmp_path, monkeypatch,
            [topic("t_9f2a")],
            [{"name": crons.DAILY_NAME, "enabled": True, "paused_at": None}],
            runner)
        assert not any("remove" in c and crons.DAILY_NAME in c for c in calls)


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