"""The rule that keeps the watchdog in step with a control command."""

from tuyabot.storage.repos import devices as devices_repo
from tuyabot.telegram import watchdog as watchdog_module


class FakeDog:
    def __init__(self, arm: bool) -> None:
        self._arm = arm
        self.armed = 0
        self.cancelled = 0

    def should_arm(self, device, role_id):
        return self._arm

    def arm(self, device):
        self.armed += 1

    def cancel(self, device_id):
        self.cancelled += 1


def _device() -> dict:
    device_id = devices_repo.create(
        {"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k",
         "type": "plug", "features": {"watchdog": True}}
    )
    return devices_repo.get(device_id)


def test_switching_on_without_the_off_right_arms(ready_db):
    dog = FakeDog(arm=True)
    watchdog_module.sync_after_control(dog, _device(), True, 1)
    assert (dog.armed, dog.cancelled) == (1, 0)


def test_switching_on_with_the_off_right_cancels_an_earlier_arm(ready_db):
    """A watchdog armed by a lesser role must not outlive the controller."""
    dog = FakeDog(arm=False)
    watchdog_module.sync_after_control(dog, _device(), True, 1)
    assert (dog.armed, dog.cancelled) == (0, 1)


def test_switching_off_always_cancels(ready_db):
    dog = FakeDog(arm=True)
    watchdog_module.sync_after_control(dog, _device(), False, 1)
    assert (dog.armed, dog.cancelled) == (0, 1)
