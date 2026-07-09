#pragma once
#include "ToolbarState.hpp"

class ButtonPlugin;
namespace h3 { struct H3AdventureMgrDlg; }

// Laduje DEF-y toolbara z H3.LodTable raz na cale zycie dialogu.
// Przekazujemy plugin do logowania (unika zaleznosci cyklicznej przez glob).
void LoadToolbarDefs(ButtonPlugin& plugin);

// Upewnia sie, ze toolbar jest gotowy dla podanego dialogu przygodowego.
// Wywolywac co klatke z HH_DlgProc.
void EnsureToolbar(h3::H3AdventureMgrDlg* advDlg);

// Zwraca indeks przycisku toolbara pod punktem (x,y) w koordynatach okna H3.
// -1 jesli poza obszarem toolbara.
int HitToolbarButton(int x, int y);

// Zwraca true tylko jesli mapa przygody jest aktualnie aktywnym,
// wierzchnim ekranem gry (nie menu glowne, nie miasto/bitwa nad mapa).
bool IsAdventureMapForeground();
