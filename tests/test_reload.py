"""Reload must terminate recorders before replacing the process."""
from threading import Event, Thread
from unittest.mock import Mock

from streamonitor.bot import Bot
from streamonitor.enums import Status
from streamonitor.manager import Manager


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
    execv = Mock()
    monkeypatch.setattr("streamonitor.manager.os.execv", execv)
    Manager([bot]).reload_process()
    assert not bot.started_recording
    assert not bot.is_alive()
    execv.assert_called_once()


def test_reload_bounds_join_and_logs_timeout(monkeypatch):
    bot = Mock()
    bot.is_alive.return_value = True
    manager = Manager([bot])
    manager.logger = Mock()
    execv = Mock()
    monkeypatch.setattr("streamonitor.manager.os.execv", execv)
    manager.reload_process()
    bot.join.assert_called_once_with(timeout=120)
    manager.logger.warning.assert_called_once()
    execv.assert_called_once()


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
