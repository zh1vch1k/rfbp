cmake_minimum_required(VERSION 3.12)

project(RFBP LANGUAGES C CXX)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(rfbp STATIC
    src/packet.cpp
    src/speck.c
    src/fsm_handshake.cpp
)

target_include_directories(rfbp PUBLIC lib)

option(BUILD_TESTS "Built tests for RFBP" ON)

IF(BUILD_TESTS)
    add_executable(rfbp_test tests/main.cpp)
    target_link_libraries(rfbp_test PRIVATE rfbp)
endif()