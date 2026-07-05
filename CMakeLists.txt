cmake_minimum_required(VERSION 3.20)
project(H3ButtonPlugin)

# Standard C++
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Ścieżki do H3Plugins i nowego H3API
# Domyślnie katalog siostrzani wobec tego repo (patrz README) - nadpisz, jeśli trzymasz H3Plugins gdzie indziej.
set(H3PLUGINS_DIR "${CMAKE_SOURCE_DIR}/../H3Plugins" CACHE PATH "Ścieżka do checkoutu H3Plugins")
set(H3API_OLD_LIB "${H3PLUGINS_DIR}/H3API/lib")        # stary lib - tylko dla Plugin.hpp
set(H3API_NEW_DIR "${CMAKE_SOURCE_DIR}/external/H3API/include")  # nowy H3API (pelny)

# Zbierz wszystkie .cpp z nowego H3API
file(GLOB_RECURSE H3API_NEW_SOURCES "${H3API_NEW_DIR}/h3api/*.cpp")

# Pliki źródłowe
add_library(H3ButtonPlugin SHARED
        # Plugin_local.cpp - nasza kopia Plugin.cpp z poprawnymi includami dla nowego H3API
        src/Plugin_local.cpp

        # Nowy H3API (external/H3API/include/h3api/**/*.cpp)
        ${H3API_NEW_SOURCES}

        # Nasze pliki
        src/dllmain.cpp
        src/ButtonPlugin.cpp
        src/TextMap.cpp
        src/ToolbarState.cpp
        src/ToolbarRenderer.cpp
        src/ToolbarLayout.cpp
        src/ToolbarActions.cpp
        src/PlayerDlg.cpp
        src/miniaudio_impl.cpp
)

# Nagłówki - nowy H3API ma priorytet, stary lib tylko dla Plugin.hpp
target_include_directories(H3ButtonPlugin PRIVATE
        ${H3API_NEW_DIR}          # nowy H3API (pierwszy - ma priorytet)
        ${H3API_OLD_LIB}          # stary lib (dla Plugin.hpp i patcher_x86.hpp)
        ${H3PLUGINS_DIR}/ThirdParty
        ${CMAKE_SOURCE_DIR}/src
        ${CMAKE_SOURCE_DIR}/external/miniaudio
)

# Linkujemy z winmm
target_link_libraries(H3ButtonPlugin PRIVATE winmm)

# Definicje preprocesora
target_compile_definitions(H3ButtonPlugin PRIVATE
        _H3API_LIBRARY_
        WIN32
        _WINDOWS
)

# Ustawienia dla MSVC
if(MSVC)
    target_compile_options(H3ButtonPlugin PRIVATE
            /W3
            /wd4996  # Disable deprecation warnings
    )

    set_target_properties(H3ButtonPlugin PROPERTIES
            RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
            LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
endif()

# Nazwa bez prefiksu "lib"
set_target_properties(H3ButtonPlugin PROPERTIES PREFIX "")
