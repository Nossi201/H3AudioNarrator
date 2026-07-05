// miniaudio implementation unit
// Ten plik musi byc skompilowany DOKLADNIE RAZ w projekcie.
// Wszystkie inne pliki dolaczaja miniaudio.h bez tego define.

#ifdef _MSC_VER
#   pragma warning(push)
#   pragma warning(disable: 4100 4244 4701 4703 4706 4996)
#endif

#define MINIAUDIO_IMPLEMENTATION
#include "miniaudio.h"

#ifdef _MSC_VER
#   pragma warning(pop)
#endif
