"""Test suite for Generic Device Registry & Capability Model (Phase A)."""

import pytest
from core.device_resolver import DeviceResolver, DeviceRecord


def test_device_record_creation():
    rec = DeviceRecord(
        id="rig_alpha",
        display_name="Workstation Alpha",
        aliases=["rig", "alpha", "the big rig"],
        operating_system="linux",
        is_local=False,
        connection_url="http://192.168.1.50:8765",
        capabilities=["local_llm", "desktop_control", "clipboard", "file_transfer"],
        roles=["inference_node", "compute"]
    )
    assert rec.id == "rig_alpha"
    assert rec.display_name == "Workstation Alpha"
    assert "local_llm" in rec.capabilities
    assert "inference_node" in rec.roles
    assert rec.is_local is False


def test_n_devices_registration():
    custom_cfg = {
        "dev_1": {
            "id": "dev_1",
            "display_name": "Living Room Mac",
            "is_local": True,
            "operating_system": "macos",
            "capabilities": ["desktop_control", "audio_io", "clipboard"],
            "roles": ["host"],
            "aliases": ["living room", "tv mac", "here"]
        },
        "dev_2": {
            "id": "dev_2",
            "display_name": "Office Linux",
            "is_local": False,
            "operating_system": "linux",
            "capabilities": ["desktop_control", "local_llm", "file_transfer"],
            "roles": ["compute"],
            "aliases": ["office", "linux box"]
        },
        "dev_3": {
            "id": "dev_3",
            "display_name": "Basement Server",
            "is_local": False,
            "operating_system": "linux",
            "capabilities": ["local_llm", "storage"],
            "roles": ["heavy_inference"],
            "aliases": ["server", "basement"]
        },
    }

    resolver = DeviceResolver(custom_cfg)
    assert len(resolver.registered_devices) == 3
    assert resolver.default_local_device == "dev_1"
    assert resolver.default_remote_device == "dev_2"

    # Capability queries
    llm_devs = resolver.find_devices_by_capability("local_llm")
    assert "dev_2" in llm_devs
    assert "dev_3" in llm_devs
    assert "dev_1" not in llm_devs

    clipboard_devs = resolver.find_devices_by_capability("clipboard")
    assert clipboard_devs == ["dev_1"]

    # Role queries
    compute_devs = resolver.find_devices_by_role("compute")
    assert compute_devs == ["dev_2"]


def test_find_device_for_local_ai():
    custom_cfg = {
        "laptop": {
            "id": "laptop",
            "display_name": "Laptop",
            "is_local": True,
            "capabilities": ["desktop_control"],
        },
        "gpu_rig": {
            "id": "gpu_rig",
            "display_name": "GPU Rig",
            "is_local": False,
            "capabilities": ["local_llm"],
        }
    }
    resolver = DeviceResolver(custom_cfg)

    # Automatic discovery of device with local_llm capability
    ai_dev = resolver.find_device_for_local_ai()
    assert ai_dev == "gpu_rig"

    # Preferred device override if valid
    ai_dev_preferred = resolver.find_device_for_local_ai(preferred_id="laptop")
    assert ai_dev_preferred == "laptop"

    # Preferred device nonexistent fallback
    ai_dev_fallback = resolver.find_device_for_local_ai(preferred_id="nonexistent")
    assert ai_dev_fallback == "gpu_rig"


def test_dynamic_runtime_device_registration_and_removal():
    resolver = DeviceResolver({})
    assert len(resolver.registered_devices) == 0

    new_dev = DeviceRecord(
        id="tablet_01",
        display_name="Field Tablet",
        aliases=["tablet", "ipad"],
        is_local=False,
        capabilities=["screen_mirror"]
    )
    resolver.register_device(new_dev)
    assert "tablet_01" in resolver.registered_devices
    assert resolver.resolve("check the tablet") == "tablet_01"

    # Unregister
    resolver.unregister_device("tablet_01")
    assert "tablet_01" not in resolver.registered_devices
    # After removal, alias should not resolve to tablet_01
    assert resolver.resolve("check the tablet") != "tablet_01"


def test_prompt_summary_generation():
    resolver = DeviceResolver({
        "node_a": {
            "id": "node_a",
            "display_name": "Node A",
            "is_local": True,
            "operating_system": "macos",
            "capabilities": ["audio_io"]
        }
    })
    summary = resolver.get_devices_prompt_summary()
    assert '"node_a": Node A' in summary
    assert "macos" in summary
    assert "audio_io" in summary
