#pragma once
#include "ToolbarState.hpp"

// Forward-declare typów H3 i patchera
namespace h3 { struct H3WindowManager; struct H3LoadedPcx16; }
class HiHook;

// Sprawdza czy prostokat [ax,ay,aw,ah] przecina [bx,by,bw,bh]
bool RectIntersects(int ax, int ay, int aw, int ah, int bx, int by, int bw, int bh);

// Wymusza przerysowanie obszaru paska (bezpieczne dla wątku hooków)
void RequestRedrawToolbarRegion();

// Rysuje caly pasek na buforze wm
void DrawToolbar(h3::H3WindowManager* wm, HiHook* h);
