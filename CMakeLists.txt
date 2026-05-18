cmake_minimum_required(VERSION 3.10)
project(WoSt)

# ============================================================================
# C++ Standard
# ============================================================================

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)


set(CMAKE_PREFIX_PATH
    ${CMAKE_PREFIX_PATH}
)

find_package(Threads REQUIRED)

# ============================================================================
# OpenMP for AppleClang
# ============================================================================

if(APPLE)

    # Homebrew libomp root
    set(LIBOMP_ROOT "/opt/homebrew/opt/libomp")

    # Compiler flags
    set(OpenMP_C_FLAGS "-Xpreprocessor -fopenmp")
    set(OpenMP_CXX_FLAGS "-Xpreprocessor -fopenmp")

    # Include path
    include_directories("${LIBOMP_ROOT}/include")

    # Library
    link_directories("${LIBOMP_ROOT}/lib")

    set(OpenMP_C_LIB_NAMES "omp")
    set(OpenMP_CXX_LIB_NAMES "omp")

    set(OpenMP_omp_LIBRARY
        "${LIBOMP_ROOT}/lib/libomp.dylib"
    )

endif()

find_package(OpenMP REQUIRED)

# ============================================================================
# Include directories
# ============================================================================

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# ============================================================================
# Sources
# ============================================================================

set(SOURCES
    main.cpp
    src/WoStGeometryBackend.cpp
    src/WoStKernel.cpp
    src/CubeOuterBoundary.cpp
)

# ============================================================================
# Executable
# ============================================================================

add_executable(wost ${SOURCES})

# ============================================================================
# Compile options
# ============================================================================

target_compile_options(wost PRIVATE
    -fopenmp
    -march=native 
    -mtune=native
    -O3
    -Wall
    -Wextra
    -funroll-loops
    -ffast-math
)

# ============================================================================
# OpenMP include dirs
# ============================================================================

target_include_directories(wost PRIVATE
    /opt/homebrew/opt/libomp/include
)

# ============================================================================
# Link
# ============================================================================

target_link_libraries(wost
    PRIVATE
    Threads::Threads
    OpenMP::OpenMP_CXX
)