"""Fixed semantic controls in the verified installed Spotify window; no input injection."""

import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import quote_plus, unquote, urlsplit

from jarvis.media_data import MediaError, MediaItem


def content_identity(value):
    if not isinstance(value, str) or len(value) > 400:
        return None
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"open.spotify.com", "xpui.app.spotify.com"}
        or parsed.port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return None
    match = re.fullmatch(
        r"/(?:intl-[a-z]{2}/)?(track|playlist|artist)/([A-Za-z0-9]{22})", parsed.path
    )
    return (match[1], match[2]) if match else None


def owner_identity(value):
    if not isinstance(value, str) or len(value) > 400:
        return None
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"open.spotify.com", "xpui.app.spotify.com"}
        or parsed.port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return None
    match = re.fullmatch(r"/user/([A-Za-z0-9._-]{1,128})", parsed.path)
    return match[1] if match else None


def normalized(value):
    return " ".join(value.split()).casefold()


def search_uri(query):
    from jarvis.media_data import safe_media_query

    if safe_media_query(query) != query:
        raise MediaError("SPOTIFY_SEARCH_QUERY_INVALID")
    # Spotify URI queries encode spaces as + and literal pluses as %2B. Raw or
    # percent-encoded spaces can be decoded into truncated activation arguments.
    return "spotify:search:" + quote_plus(query, safe="")


def search_matches(value, query):
    # The Store client's protocol navigation rewrites spaces as plus characters.
    # Accept only this exact representation of the admitted query, not fuzzy text.
    return value == query or value == query.replace(" ", "+")


def filter_route_matches(value, query, kind):
    if not isinstance(value, str) or len(value) > 1200:
        return False
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"open.spotify.com", "xpui.app.spotify.com"}
        or parsed.port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return False
    parts = parsed.path.split("/")
    return (
        len(parts) == 4
        and parts[1] == "search"
        and parts[3] == ("playlists" if kind == "playlist" else "tracks")
        and search_matches(unquote(parts[2]), query)
    )


def native_song_record(label, creator, artist_ids, runtime):
    suffix = " by " + creator
    prefix = next((p for p in ("Play ", "Pause ") if label.startswith(p)), None)
    if not prefix or not creator or not artist_ids or not label.endswith(suffix):
        raise MediaError("SPOTIFY_SONG_ROW_IDENTITY_UNAVAILABLE")
    title = label[len(prefix) : -len(suffix)]
    if not title or len(title) > 240 or any(ord(c) < 32 for c in title + creator):
        raise MediaError("SPOTIFY_RESULT_LABEL_INVALID")
    signature = json.dumps([title, creator, artist_ids, runtime], separators=(",", ":"))
    return {
        "id": "native_" + hashlib.sha256(signature.encode()).hexdigest()[:32],
        "title": title,
        "creator": creator,
        "kind": "track",
        "uri": "",
        "runtime": tuple(runtime),
        "source": "row",
    }


class SpotifyAccessibility:
    def __init__(self):
        import comtypes.client

        from jarvis.application_data import ApplicationsConfig
        from jarvis.application_identity import signer
        from jarvis.application_worker import ApplicationNative, catalog

        self.config = ApplicationsConfig(enabled=True)
        # This measured adapter supports the official Store package on this PC.
        # A display name or arbitrary model path is never a launch/app identity.
        apps = [
            a
            for a in catalog(self.config)[0]
            if a.launch_id == "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"
        ]
        if len(apps) != 1 or not signer(apps[0].executable):
            raise MediaError("SPOTIFY_INSTALLED_IDENTITY_UNAVAILABLE")
        self.app = apps[0]
        self.native = ApplicationNative()
        self.module = comtypes.client.GetModule(
            str(Path(os.environ["WINDIR"]) / "System32/UIAutomationCore.dll")
        )
        self.uia = comtypes.client.CreateObject(
            self.module.CUIAutomation, interface=self.module.IUIAutomation
        )
        self.window = None
        self.query = ""
        self.kind = "track"
        self.bindings = {}
        self.admitted = False

    def root(self):
        from jarvis.application_tools import identity

        windows = self.native.inventory([self.app], self.config)
        if len(windows) != 1:
            raise MediaError("SPOTIFY_OPEN_ONE_VISIBLE_WINDOW")
        record = windows[0]
        if self.window is not None and identity(record) != identity(self.window):
            raise MediaError("SPOTIFY_WINDOW_CHANGED")
        # Reject locked/non-default desktops without comparing unrelated input.
        self.native.activity()
        if self.native.user.IsIconic(record["hwnd"]):
            raise MediaError("SPOTIFY_WINDOW_MINIMIZED")
        if not self.native.user.IsWindowEnabled(record["hwnd"]) or self.native.has_dialog(
            record["pid"], record["hwnd"]
        ):
            raise MediaError("SPOTIFY_WINDOW_UNAVAILABLE")
        self.window = record
        return self.uia.ElementFromHandle(record["hwnd"])

    def nodes(self, root, condition):
        nodes = root.FindAll(4, condition)
        if nodes.Length > 2500:
            raise MediaError("SPOTIFY_ACCESSIBILITY_LIMIT")
        return [nodes.GetElement(i) for i in range(nodes.Length)]

    def begin_search(self):
        # A new owner search may address the verified app after it was closed and
        # reopened. Old result references never follow that replacement window.
        # Pin its identity again here; every subsequent read/delivery still checks
        # this exact window, including changes during the search itself.
        self.window = None
        self.query = ""
        self.bindings = {}
        return self.root()

    def main(self, root):
        nodes = self.nodes(root, self.uia.CreatePropertyCondition(30101, "main"))
        if len(nodes) != 1:
            raise MediaError("SPOTIFY_MAIN_VIEW_UNAVAILABLE")
        return nodes[0]

    def search_field(self, root):
        nodes = self.nodes(
            root, self.uia.CreatePropertyCondition(30005, "What do you want to play?")
        )
        nodes = [n for n in nodes if n.CurrentControlType in {50003, 50004}]
        if len(nodes) != 1 or not nodes[0].CurrentIsEnabled or nodes[0].CurrentIsOffscreen:
            raise MediaError("SPOTIFY_SEARCH_CONTROL_UNAVAILABLE")
        pattern = (
            nodes[0].GetCurrentPattern(10002).QueryInterface(self.module.IUIAutomationValuePattern)
        )
        if pattern.CurrentIsReadOnly:
            raise MediaError("SPOTIFY_SEARCH_READ_ONLY")
        return nodes[0], pattern

    def invoke(self, element, gate):
        if not element.CurrentIsEnabled or element.CurrentIsOffscreen:
            raise MediaError("SPOTIFY_CONTROL_UNAVAILABLE")
        if element.CurrentControlType == 50002 and element.CurrentName in {"Songs", "Playlists"}:
            pattern = element.GetCurrentPattern(10015).QueryInterface(
                self.module.IUIAutomationTogglePattern
            )
            if pattern.CurrentToggleState == 1:
                return
            deliver = pattern.Toggle
        elif element.CurrentControlType in {50013, 50019} and element.CurrentName in {
            "Songs",
            "Playlists",
        }:
            pattern = element.GetCurrentPattern(10010).QueryInterface(
                self.module.IUIAutomationSelectionItemPattern
            )
            if pattern.CurrentIsSelected:
                return
            deliver = pattern.Select
        else:
            pattern = element.GetCurrentPattern(10000).QueryInterface(
                self.module.IUIAutomationInvokePattern
            )
            deliver = pattern.Invoke
        root = self.root()  # Revalidate the exact user/session/window before delivery.
        if self.query and not search_matches(self.search_field(root)[1].CurrentValue, self.query):
            raise MediaError("SPOTIFY_SEARCH_CHANGED")
        if element.CurrentName in {"Songs", "Playlists"}:
            links = self.nodes(
                self.main(root), self.uia.CreatePropertyCondition(30005, element.CurrentName)
            )
            if not any(
                n.CurrentControlType == 50005
                and filter_route_matches(self.uri(n), self.query, self.kind)
                for n in links
            ):
                raise MediaError("SPOTIFY_FILTER_QUERY_CHANGED")
        gate()
        self.admitted = True
        deliver()

    def no_results(self, main):
        texts = self.nodes(main, self.uia.CreatePropertyCondition(30003, 50020))
        return any(n.CurrentName.startswith("No results found") for n in texts)

    def commit_search(self, query, gate):
        root = self.root()
        forms = self.nodes(root, self.uia.CreatePropertyCondition(30101, "search"))
        forms = [
            form
            for form in forms
            if self.nodes(
                form, self.uia.CreatePropertyCondition(30005, "What do you want to play?")
            )
        ]
        if len(forms) != 1 or not search_matches(
            self.search_field(forms[0])[1].CurrentValue, query
        ):
            raise MediaError("SPOTIFY_SEARCH_FORM_CHANGED")
        buttons = self.nodes(forms[0], self.uia.CreatePropertyCondition(30005, "Search"))
        buttons = [n for n in buttons if n.CurrentControlType == 50000]
        if len(buttons) != 1:
            raise MediaError("SPOTIFY_SEARCH_SUBMIT_UNAVAILABLE")
        self.invoke(buttons[0], gate)

    async def settled_search_value(self, gate):
        """Read a temporarily rebuilding search control, without repeating delivery."""
        import asyncio

        while True:
            gate()
            try:
                return self.search_field(self.root())[1].CurrentValue
            except MediaError as error:
                if error.code != "SPOTIFY_SEARCH_CONTROL_UNAVAILABLE":
                    raise
                await asyncio.sleep(0.1)

    def filter_selected(self, element):
        if element.CurrentControlType == 50002:
            pattern = element.GetCurrentPattern(10015).QueryInterface(
                self.module.IUIAutomationTogglePattern
            )
            return pattern.CurrentToggleState == 1
        if element.CurrentControlType in {50013, 50019}:
            pattern = element.GetCurrentPattern(10010).QueryInterface(
                self.module.IUIAutomationSelectionItemPattern
            )
            return bool(pattern.CurrentIsSelected)
        return False

    async def search(self, query, kind, gate):
        from winrt.windows.foundation import Uri
        from winrt.windows.system import Launcher, LauncherOptions

        self.admitted = False
        self.root()
        options = LauncherOptions()
        options.target_application_package_family_name = "SpotifyAB.SpotifyMusic_zpdnekdrzrea0"
        # Target the verified package explicitly. Never use the global default
        # protocol handler, ShellExecute, an executable argument or a model URI.
        uri = Uri(search_uri(query))
        gate()
        self.admitted = True
        if not await Launcher.launch_uri_with_options_async(uri, options):
            raise MediaError("SPOTIFY_SEARCH_NAVIGATION_UNAVAILABLE")
        self.query, self.kind, self.bindings = query, kind, {}
        import asyncio

        await asyncio.sleep(0.5)
        while True:
            gate()
            current = await self.settled_search_value(gate)
            if search_matches(current, query):
                break
            await asyncio.sleep(0.05)
        self.commit_search(query, gate)
        await asyncio.sleep(0.5)
        label = "Playlists" if kind == "playlist" else "Songs"
        filter_invoked = False
        while True:
            gate()
            if not search_matches(await self.settled_search_value(gate), query):
                await asyncio.sleep(0.1)
                continue
            root = self.root()
            nodes = self.nodes(self.main(root), self.uia.CreatePropertyCondition(30005, label))
            if not any(
                n.CurrentControlType == 50005 and filter_route_matches(self.uri(n), query, kind)
                for n in nodes
            ):
                # Wait for a filter bound to this query. A stale link must never
                # navigate to an earlier search, and All is not a fallback.
                await asyncio.sleep(0.1)
                continue
            controls = [
                n
                for n in nodes
                if n.CurrentControlType in {50000, 50002, 50005, 50013, 50019}
                and n.CurrentIsEnabled
                and not n.CurrentIsOffscreen
            ]
            filters = [n for n in controls if n.CurrentControlType in {50002, 50013, 50019}]
            if filters:
                controls = filters
            if len(controls) == 1:
                if self.filter_selected(controls[0]):
                    break
                if not filter_invoked:
                    self.invoke(controls[0], gate)
                    filter_invoked = True
                # Re-read selected state after the one allowed filter delivery.
                # Empty All results do not bypass the requested category either.
            await asyncio.sleep(0.1)

    def uri(self, element):
        try:
            return (
                element.GetCurrentPattern(10018)
                .QueryInterface(self.module.IUIAutomationLegacyIAccessiblePattern)
                .CurrentValue
            )
        except Exception:
            return ""

    def container(self, link, kind):
        walker = self.uia.ControlViewWalker
        node = link
        for _ in range(8):
            node = walker.GetParentElement(node)
            if not node:
                break
            if kind == "track" and node.GetCurrentPropertyValue(30101) == "row":
                return node
            if kind == "playlist":
                buttons = self.nodes(node, self.uia.CreatePropertyCondition(30003, 50000))
                if any(
                    n.CurrentName in {"Play", "Pause"}
                    or n.CurrentName.startswith(("Play ", "Pause "))
                    for n in buttons
                ):
                    links = self.nodes(node, self.uia.CreatePropertyCondition(30003, 50005))
                    ids = {content_identity(self.uri(n)) for n in links}
                    if len({v for v in ids if v and v[0] == "playlist"}) == 1:
                        return node
        raise MediaError("SPOTIFY_RESULT_STRUCTURE_UNAVAILABLE")

    def results(self, limit):
        root = self.root()
        if not search_matches(self.search_field(root)[1].CurrentValue, self.query):
            raise MediaError("SPOTIFY_SEARCH_CHANGED")
        main = self.main(root)
        if self.kind == "track":
            rows = self.nodes(main, self.uia.CreatePropertyCondition(30101, "row"))
            found = []
            for row in rows:
                if row.CurrentIsOffscreen:
                    continue
                buttons = self.nodes(row, self.uia.CreatePropertyCondition(30003, 50000))
                plays = [
                    n
                    for n in buttons
                    if n.CurrentName in {"Play", "Pause"}
                    or n.CurrentName.startswith(("Play ", "Pause "))
                ]
                if len(plays) != 1:
                    continue
                identity_label = plays[0].CurrentName
                if identity_label in {"Play", "Pause"}:
                    # The active row changes to a generic Pause label. Its exact
                    # More-options label retains title/artist; read it, never invoke it.
                    labels = [
                        n.CurrentName.removeprefix("More options for ")
                        for n in buttons
                        if n.CurrentName.startswith("More options for ")
                    ]
                    if len(labels) > 1:
                        raise MediaError("SPOTIFY_SONG_ROW_IDENTITY_UNAVAILABLE")
                    if labels:
                        identity_label = "Play " + labels[0]
                links = self.nodes(row, self.uia.CreatePropertyCondition(30003, 50005))
                artists = [
                    (n.CurrentName, item[1])
                    for n in links
                    if (item := content_identity(self.uri(n))) and item[0] == "artist"
                ]
                artists = list(dict.fromkeys(artists))
                creator = ", ".join(name for name, _ in artists)
                if len(creator) > 160:
                    raise MediaError("SPOTIFY_RESULT_LABEL_INVALID")
                tracks = [
                    (n, item)
                    for n in links
                    if (item := content_identity(self.uri(n))) and item[0] == "track"
                ]
                if len(tracks) == 1 and creator:
                    link, item = tracks[0]
                    title = link.CurrentName
                    if identity_label in {"Play", "Pause"}:
                        identity_label = "Play " + title + " by " + creator
                    names = {
                        p + title + suffix
                        for p in ("Play ", "Pause ")
                        for suffix in ("", " by " + creator)
                    }
                    if not title or len(title) > 240 or identity_label not in names:
                        raise MediaError("SPOTIFY_SONG_ROW_IDENTITY_UNAVAILABLE")
                    record = {
                        "id": item[1],
                        "title": title,
                        "creator": creator,
                        "kind": "track",
                        "uri": self.uri(link),
                        "runtime": tuple(row.GetRuntimeId()),
                        "source": "row",
                    }
                else:
                    if identity_label in {"Play", "Pause"}:
                        raise MediaError("SPOTIFY_SONG_ROW_IDENTITY_UNAVAILABLE")
                    if not identity_label.endswith(" by " + creator):
                        identity_label += " by " + creator
                    record = native_song_record(
                        identity_label,
                        creator,
                        [item_id for _, item_id in artists],
                        tuple(row.GetRuntimeId()),
                    )
                found.append(record)
                if len(found) == limit:
                    break
            if not found and not self.no_results(main):
                raise MediaError("SPOTIFY_RESULTS_LOADING")
            return found
        links = self.nodes(main, self.uia.CreatePropertyCondition(30003, 50005))
        found = {}
        for link in links:
            uri = self.uri(link)
            item = content_identity(uri)
            if not item or item[0] != self.kind or link.CurrentIsOffscreen:
                continue
            title = link.CurrentName
            if not title or len(title) > 240:
                raise MediaError("SPOTIFY_RESULT_LABEL_INVALID")
            if item[1] in found:
                if found[item[1]]["title"] != title:
                    raise MediaError("SPOTIFY_RESULT_IDENTITY_AMBIGUOUS")
                continue
            container = self.container(link, self.kind)
            creator = ""
            if self.kind == "track":
                artists = self.nodes(container, self.uia.CreatePropertyCondition(30003, 50005))
                creator = ", ".join(
                    dict.fromkeys(
                        n.CurrentName
                        for n in artists
                        if (content_identity(self.uri(n)) or (None,))[0] == "artist"
                    )
                )[:160]
            else:
                buttons = self.nodes(container, self.uia.CreatePropertyCondition(30003, 50000))
                prefixes = ("Play " + title + " by ", "Pause " + title + " by ")
                names = [n.CurrentName for n in buttons if n.CurrentName.startswith(prefixes)]
                if len(names) == 1:
                    prefix = next(p for p in prefixes if names[0].startswith(p))
                    creator = names[0][len(prefix) :][:160]
                owner_links = self.nodes(container, self.uia.CreatePropertyCondition(30003, 50005))
                owners = list(
                    dict.fromkeys(
                        (owner, n.CurrentName)
                        for n in owner_links
                        if (owner := owner_identity(self.uri(n)))
                    )
                )
                if len(owners) > 1:
                    raise MediaError("SPOTIFY_PLAYLIST_OWNER_AMBIGUOUS")
                if owners:
                    owner_name = owners[0][1]
                    if (
                        not owner_name
                        or len(owner_name) > 160
                        or (creator and normalized(creator) != normalized(owner_name))
                    ):
                        raise MediaError("SPOTIFY_PLAYLIST_OWNER_CHANGED")
                    creator = owner_name
            found[item[1]] = {
                "id": item[1],
                "title": title,
                "creator": creator,
                "kind": self.kind,
                "uri": uri,
                "runtime": tuple(link.GetRuntimeId()),
            }
            if len(found) == limit:
                break
        if not found and not self.no_results(main):
            raise MediaError("SPOTIFY_RESULTS_LOADING")
        return list(found.values())

    def bind(self, records):
        from uuid import uuid4

        self.bindings = {"media_" + uuid4().hex: record for record in records}
        return [
            MediaItem(
                reference=ref,
                item_id=r["id"],
                title=r["title"],
                creator=r["creator"],
                content_type=r["kind"],
            )
            for ref, r in self.bindings.items()
        ]

    def selected(self, reference):
        bound = self.bindings.get(reference)
        if not bound:
            raise MediaError("SPOTIFY_RESULT_REFERENCE_EXPIRED")
        records = self.results(5)
        matched = [r for r in records if r == bound]
        if len(matched) != 1:
            raise MediaError("SPOTIFY_RESULT_CHANGED")
        return bound

    def playback_control(self, reference, playing=False):
        bound = self.selected(reference)
        root = self.root()
        if bound.get("source") == "row":
            rows = self.nodes(self.main(root), self.uia.CreatePropertyCondition(30101, "row"))
            rows = [n for n in rows if tuple(n.GetRuntimeId()) == bound["runtime"]]
            if len(rows) != 1:
                raise MediaError("SPOTIFY_RESULT_CHANGED")
            label = ("Pause " if playing else "Play ") + bound["title"]
            labels = {label + " by " + bound["creator"]}
            labels.add("Pause" if playing else "Play")
            if bound["uri"]:
                labels.add(label)
            buttons = self.nodes(rows[0], self.uia.CreatePropertyCondition(30003, 50000))
            matches = [n for n in buttons if n.CurrentName in labels and not n.CurrentIsOffscreen]
            if len(matches) != 1:
                raise MediaError("SPOTIFY_EXACT_PLAY_CONTROL_UNAVAILABLE")
            return matches[0]
        links = self.nodes(self.main(root), self.uia.CreatePropertyCondition(30003, 50005))
        links = [
            n
            for n in links
            if tuple(n.GetRuntimeId()) == bound["runtime"]
            and self.uri(n) == bound["uri"]
            and n.CurrentName == bound["title"]
        ]
        if len(links) != 1:
            raise MediaError("SPOTIFY_RESULT_CHANGED")
        container = self.container(links[0], bound["kind"])
        candidate_links = self.nodes(container, self.uia.CreatePropertyCondition(30003, 50005))
        content_ids = {
            v
            for n in candidate_links
            if (v := content_identity(self.uri(n))) and v[0] == bound["kind"]
        }
        if content_ids != {(bound["kind"], bound["id"])}:
            raise MediaError("SPOTIFY_PLAY_TARGET_AMBIGUOUS")
        prefix = ("Pause " if playing else "Play ") + bound["title"]
        buttons = self.nodes(container, self.uia.CreatePropertyCondition(30003, 50000))
        names = {prefix, prefix + " by " + bound["creator"], "Pause" if playing else "Play"}
        matches = [n for n in buttons if n.CurrentName in names and not n.CurrentIsOffscreen]
        if len(matches) != 1:
            raise MediaError("SPOTIFY_EXACT_PLAY_CONTROL_UNAVAILABLE")
        return matches[0]

    def play(self, reference, gate):
        self.admitted = False
        element = self.playback_control(reference)
        self.invoke(element, gate)

    def context_playing(self, reference):
        try:
            self.playback_control(reference, playing=True)
            return True
        except MediaError:
            return False
