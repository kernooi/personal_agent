"""Generate candidates from controller scope; final parsing and authorization remain strict."""

from jarvis.models import BOUNDARY_M2


def candidate_schema(scope):
    schema = BOUNDARY_M2.json_schema()
    definitions = schema["$defs"]
    if scope.app_id != "notepad":
        schema["oneOf"] = [item for item in schema["oneOf"] if item["$ref"] != "#/$defs/ProposeM2"]
        schema["discriminator"]["mapping"].pop("propose_action")
        for name in (
            "ProposeM2",
            "NotepadAction",
            "NotepadArguments",
            "WindowAction",
            "WindowArguments",
        ):
            definitions.pop(name)
    else:
        action_name = "NotepadAction" if scope.effect == "open" else "WindowAction"
        definitions["ProposeM2"]["properties"]["action"] = {"$ref": f"#/$defs/{action_name}"}
        if scope.effect != "open":
            definitions["WindowAction"]["properties"]["capability"] = {
                "const": f"windows.{scope.effect}",
                "type": "string",
            }
            definitions["WindowArguments"]["properties"]["window_ref"] = {
                "const": scope.window_ref,
                "type": "string",
            }
    return schema
