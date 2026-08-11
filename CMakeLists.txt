cmake_minimum_required(VERSION 3.12)

project(RFBP LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(rfbp_test
main.cpp
packet.hpp)
