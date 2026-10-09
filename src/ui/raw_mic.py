"""
Raw microphone: ask the browser for the unprocessed mic signal.

st.audio_input requests getUserMedia({audio: true}); Chrome-based browsers (Chrome,
Comet, Edge, Brave) then apply automatic gain control, noise suppression and echo
cancellation. On speech that gets quieter towards the end, the noise suppressor
removes the tail ("vereinbaren" -> "vereinen"). Streamlit has no option for this,
so a zero-height component wraps the parent page's getUserMedia once, turning those
three off unless the caller asked for something specific. Toggle: settings
"raw_microphone" (sidebar, default on); turning it off restores the browser default.
"""

from __future__ import annotations

import streamlit.components.v1 as components

_JS = """
<script>
(function () {
  try {
    const md = window.parent && window.parent.navigator && window.parent.navigator.mediaDevices;
    if (!md || !md.getUserMedia) return;
    const w = window.parent;
    if (!w.__mioOrigGUM) w.__mioOrigGUM = md.getUserMedia.bind(md);
    w.__mioRawMic = %s;
    if (w.__mioWrapped) return;
    w.__mioWrapped = true;
    md.getUserMedia = function (c) {
      if (w.__mioRawMic && c && c.audio) {
        const raw = {echoCancellation: false, noiseSuppression: false, autoGainControl: false};
        c = Object.assign({}, c, {audio: c.audio === true ? raw : Object.assign({}, raw, c.audio)});
      }
      return w.__mioOrigGUM(c);
    };
  } catch (e) { /* cross-origin or old browser: leave the default */ }
})();
</script>
"""


def apply(settings: dict) -> None:
    """Call once per render, before st.audio_input."""
    components.html(_JS % ("true" if settings.get("raw_microphone", True) else "false"), height=0)
