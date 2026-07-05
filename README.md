# H3ButtonPlugin

Plugin (DLL) do Heroes of Might and Magic III (HD Mod / H3API), dodający pasek narzędzi na mapie przygody
do sterowania odtwarzaniem audio (Play/Pauza/Next/Previous/Menu) oraz automatyczne odtwarzanie narracji
ElevenLabs wykrywanej po treści okien dialogowych kampanii.

## Wymagania

- Visual Studio z obsługą C++ i CMake (testowane z instalacją w `C:\Program Files\Microsoft Visual Studio\18\Community`)
- CMake 3.20+
- Sąsiedni checkout [RoseKavalier/H3Plugins](https://github.com/RoseKavalier/H3Plugins) — patrz niżej

## Zależności zewnętrzne

- **`external/H3API`** — git submodule ([RoseKavalier/H3API](https://github.com/RoseKavalier/H3API)). Po sklonowaniu:
  ```
  git submodule update --init
  ```
  (albo `git clone --recurse-submodules` od razu).
- **`external/miniaudio`** — wendorowany single-header (`miniaudio.h`), zwykłe pliki repo, nic do inicjalizacji.
- **`tools/chronicles_voiceover`** — git submodule ([Nossi201/H3-VoiceOver-Pack](https://github.com/Nossi201/H3-VoiceOver-Pack)),
  wyekstrahowane teksty i wygenerowane audio narracji kampanii Heroes Chronicles. Opcjonalny — plugin buduje się
  i działa bez tego (to tylko dane runtime dla auto-play narracji). Inicjalizacja: `git submodule update --init tools/chronicles_voiceover`.
- **`../H3Plugins`** — **NIE jest submodułem tego repo**, musi być sklonowany osobno jako katalog siostrzany
  (`plugin/H3Plugins` obok `plugin/H3ButtonPlugin`):
  ```
  git clone https://github.com/RoseKavalier/H3Plugins.git
  ```
  `CMakeLists.txt` czyta stamtąd `H3API/lib` (starsze `Plugin.hpp`/`patcher_x86.hpp`, na których bazuje
  `src/Plugin_local.cpp`) oraz `ThirdParty/` (`json.hpp`, `stb_image.h`, `stb_image_resize.h`, `INIReader.h`,
  `era.hpp`). Domyślnie `H3PLUGINS_DIR` wskazuje na katalog siostrzani (`../H3Plugins`); jeśli trzymasz go
  gdzie indziej, nadpisz przy konfiguracji: `cmake -B build -DH3PLUGINS_DIR=C:/sciezka/do/H3Plugins`.

## Build

CMake re-konfiguruje się automatycznie przy zmianie `CMakeLists.txt`, więc zwykle wystarczy:
```
cmake --build build --config Release
```
Wynik: `build\bin\Release\H3ButtonPlugin.dll`.

## Deploy do gry

`build_deploy.bat` (build + `deploy.ps1`) kopiuje DLL i `text_map_with_filter.txt` do zainstalowanych kopii
gry. **Ścieżki w `deploy.ps1` są wpisane na sztywno** (`$pluginRoot`, foldery `_HD3_Data\Packs\...`) —
dostosuj je do swojego układu katalogów przed użyciem.

Plugin w runtime korzysta też z **`H3.LodTable.dll`** (buduje się z pluginu `H3.LodTable` w `H3Plugins`) —
to zależność uruchomieniowa dostarczana przez HD Mod, nie jest częścią tego repo; musi już być obecna
w folderze `_HD3_Data\Packs\` gry.

## tools/ — generowanie audio (Python)

Skrypty w `tools/` wyciągają teksty kampanii z plików gry i generują do nich narrację przez ElevenLabs API.
Zależności: `pip install -r tools/requirements.txt` (Pillow, elevenlabs).

Wymagają zmiennej środowiskowej:
```
setx ELEVENLABS_API_KEY "twoj-klucz"
```
(albo ustaw ją w bieżącej sesji przed uruchomieniem skryptu). Bez tego skrypty generujące audio
(`generate_dialogue.py`, `generate_mixed_audio.py`, `generate_woj_campaign.py`) zakończą się błędem.
