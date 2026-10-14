"""Open desktop chat using the same private setup as Chat-JarvisAll.py."""

import importlib.util
import os
from pathlib import Path

from jarvis.gui import main
from jarvis.gui_startup import StartupServices

if __name__ == "__main__":
    helper = Path(__file__).with_name("Chat-JarvisAll.py")
    spec = importlib.util.spec_from_file_location("jarvis_local_launcher", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    services = StartupServices(Path(os.environ["LOCALAPPDATA"]) / "Jarvis")
    main(module.chat_command, helper.parent.parent, prepare=services.prepare)
