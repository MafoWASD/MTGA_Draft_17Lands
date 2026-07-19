# Arena Pack Overlay Mod (BepInEx 5)

**Status: Phase 0 spike / not yet distributed.** This is a minimal Harmony patch used to
validate that MTG Arena's draft-pack grid layout can be read directly from the game's own
data, as a more reliable alternative to the OCR-based approach in `src/card_name_ocr.py`. See
the plan this was built from for full context.

## What it does right now

Patches `Wotc.Mtga.Wrapper.Draft.DraftPackHolder.LayoutCards` (found via decompiling `Core.dll`
with [ilspycmd](https://github.com/icsharpcode/ILSpy)). That method assigns each draft-pack
card's on-screen grid position purely from its index in the already-populated
`_allCardViews` list (row = index / columnCount, column = index % columnCount) — and that
list's order is Arena's own final display order, already re-sorted by
`CardSorter.Sort(..., SortTypeFilters.DraftPack)` before layout happens. This is the confirmed
root cause of why the draft log's raw pack-card order never matches the on-screen grid.

The patch logs `[index]=grpId` pairs (Arena's internal card ID, `MtgCardInstance.GrpId`) to
BepInEx's log every time a pack is laid out.

## ⚠️ Never commit or distribute Wizards' game assemblies

`bepinex_mod/lib/` (git-ignored) must contain your own local copies of the following files
from your own Arena install, copied there by you before building — **do not** commit them,
attach them to a release, or share them in any form. They are Wizards of the Coast's
copyrighted compiled game code, referenced here only so the C# compiler can resolve types at
build time:

```
bepinex_mod/lib/
  Core.dll
  SharedClientCore.dll
  Assembly-CSharp.dll
  UnityEngine.dll
  UnityEngine.CoreModule.dll
  Unity.TextMeshPro.dll
  UnityEngine.UI.dll
  UnityEngine.UIModule.dll
  Newtonsoft.Json.dll
  0Harmony.dll        (from BepInEx/core, see install step 1 below)
  BepInEx.dll          (from BepInEx/core, see install step 1 below)
```

All of these live in `<Arena install>\MTGA_Data\Managed\` (the game assemblies) and
`<Arena install>\BepInEx\core\` (the BepInEx/Harmony assemblies, after step 1 below).

The compiled output of *this* project (`ArenaPackOverlayMod.dll`) contains none of that code —
only IL that calls into it via reflection/Harmony at runtime — and is fine to build, keep, and
eventually distribute.

## Building and installing locally

1. **Install BepInEx 5** into your Arena install folder (the one containing `MTGA.exe`) by
   extracting the [win_x64 release zip](https://github.com/BepInEx/BepInEx/releases) there.
   Launch Arena once and quit — this generates `BepInEx/plugins/`, `BepInEx/config/`, and
   `BepInEx/LogOutput.log`.
2. Copy the DLLs listed above into `bepinex_mod/lib/` (git-ignored).
3. Build:
   ```
   dotnet build bepinex_mod/src/ArenaPackOverlayMod.csproj
   ```
4. Copy `bepinex_mod/src/bin/Debug/net472/ArenaPackOverlayMod.dll` into your Arena install's
   `BepInEx/plugins/` folder.
5. Launch Arena, start (or resume) a draft. Check
   `<Arena install>/BepInEx/LogOutput.log` for `[PackLayout]` lines.

## Risk notes

This mod injects into Arena's process and patches its running code — a materially different
(and higher) risk category than the rest of this repo, which only reads the log file and the
user's own screen. The patch here is intentionally read-only (a Harmony `Prefix` that only logs
— it never mutates arguments, return values, or game state) to keep blast radius minimal.
Arena patches can silently break this hook at any time; if `[PackLayout]` lines stop appearing
after an Arena update, the class/method has likely changed and needs re-locating via the same
decompile-and-search approach.
