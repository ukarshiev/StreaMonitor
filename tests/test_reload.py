"""Reload must stop recorders and exit for the container supervisor."""
from threading import Event, Thread
from unittest.mock import Mock

from streamonitor.bot import Bot
from streamonitor.enums import Status
from streamonitor.manager import Manager
from streamonitor.managers.httpmanager.httpmanager import HTTPManager


def test_reload_prevents_restart_during_stop(monkeypatch):
    class RacingBot(Thread):
        def __init__(self):
            super().__init__(daemon=True)
            self.quitting = False
            self.stopped = Event()
            self.retried = Event()
            self.started_recording = False

        def run(self):
            self.stopped.wait(2)
            self.started_recording = not self.quitting
            self.retried.set()

        def stop(self, *args):
            self.stopped.set()
            assert self.retried.wait(2)
            self.quitting = True

    bot = RacingBot()
    bot.start()
    execv = Mock(side_effect=AssertionError("reload must not exec"))
    exit_process = Mock()
    monkeypatch.setattr("streamonitor.manager.os.execv", execv)
    monkeypatch.setattr("streamonitor.manager.os._exit", exit_process)
    Manager([bot]).reload_process()
    assert not bot.started_recording
    assert not bot.is_alive()
    exit_process.assert_called_once_with(3)
    execv.assert_not_called()


def test_reload_bounds_join_and_logs_timeout(monkeypatch):
    bot = Mock()
    bot.is_alive.return_value = True
    manager = Manager([bot])
    manager.logger = Mock()
    execv = Mock(side_effect=AssertionError("reload must not exec"))
    exit_process = Mock()
    monkeypatch.setattr("streamonitor.manager.os.execv", execv)
    monkeypatch.setattr("streamonitor.manager.os._exit", exit_process)
    manager.reload_process()
    bot.join.assert_called_once_with(timeout=120)
    manager.logger.warning.assert_called_once()
    exit_process.assert_called_once_with(3)
    execv.assert_not_called()


def test_reload_flags_all_bots_then_stops_all_before_join_and_exit(monkeypatch):
    events = []
    bots = [Mock(quitting=False), Mock(quitting=False)]
    for index, bot in enumerate(bots):
        bot.is_alive.side_effect = [True, False]

        def stop(*args, index=index):
            assert all(bot.quitting for bot in bots)
            assert args == (None, None, True)
            events.append(("stop", index))

        bot.stop.side_effect = stop
        bot.join.side_effect = lambda *, timeout, index=index: events.append(
            ("join", index, timeout)
        )
    monkeypatch.setattr(
        "streamonitor.manager.os._exit", lambda code: events.append(("exit", code))
    )
    monkeypatch.setattr(
        "streamonitor.manager.os.execv", Mock(side_effect=AssertionError("must not exec"))
    )
    Manager(bots).reload_process()
    assert events == [
        ("stop", 0), ("stop", 1), ("join", 0, 120), ("join", 1, 120), ("exit", 3)
    ]


def test_http_reload_replies_before_stopping_in_background(monkeypatch):
    from flask import Flask

    apps = []
    monkeypatch.setattr(Flask, "run", lambda app, **kwargs: apps.append(app))
    monkeypatch.setattr(
        "streamonitor.managers.httpmanager.httpmanager.WEBSERVER_PASSWORD", "test-only"
    )
    stopping = Event()
    release_stop = Event()
    exited = Event()
    closed = Event()
    exit_codes = []
    worker_threads = []

    class BlockingBot:
        quitting = False

        def stop(self, *args):
            from threading import current_thread

            assert self.quitting
            worker_threads.append(current_thread())
            stopping.set()
            assert release_stop.wait(5)

        def is_alive(self):
            return False

    def exit_process(code):
        exit_codes.append(code)
        exited.set()

    monkeypatch.setattr("streamonitor.manager.os._exit", exit_process)
    monkeypatch.setattr(
        "streamonitor.manager.os.execv", Mock(side_effect=AssertionError("must not exec"))
    )
    manager = HTTPManager([BlockingBot()])
    manager.run()
    client = apps[0].test_client()
    assert client.get("/api/command?command=reload").status_code == 401
    assert not stopping.is_set()
    response = client.get(
        "/api/command?command=reload", auth=("admin", "test-only"), buffered=False
    )
    assert response.status_code == 200
    assert response.data == b"Reloading"
    assert not stopping.is_set()
    assert not exited.is_set()

    def close_response():
        response.close()
        closed.set()

    request_thread = Thread(target=close_response, daemon=True)
    request_thread.start()
    try:
        assert stopping.wait(2)
        assert closed.wait(1), "HTTP worker must not wait for recorders to stop"
        assert worker_threads[0] is not request_thread
        assert not exited.is_set()
    finally:
        release_stop.set()
        request_thread.join(timeout=2)
        assert exited.wait(2)
        for worker in worker_threads:
            if worker is not request_thread:
                worker.join(timeout=2)
    assert exit_codes == [3]


def test_stop_during_url_lookup_never_starts_ffmpeg():
    class LookupBot(Bot):
        siteslug = "test"

        def cache_file_list(self):
            pass

        def getWebsiteURL(self):
            return "test://alice"

        def getStatus(self):
            return Status.PUBLIC

        def getVideoUrl(self):
            self.stop(None, None, True)
            return "test://video"

    bot = LookupBot("alice")
    bot.getVideo = Mock(return_value=True)
    bot.genOutFilename = Mock(return_value="unused.mkv")
    bot.restart()
    bot.run()
    bot.getVideo.assert_not_called()
