#pragma once

#include "packet.hpp"

namespace rfbp::adapter {
    enum class ControllerType : uint8_t {
        NORMALIZED = 0,
        DUALSENSE,
        XBOX,
        GENERIC
    };

    enum class ButtonMask : uint8_t {
        BTN_L_STICK  = (1 << 0),
        BTN_R_STICK  = (1 << 1),
        BTN_L_BUMPER = (1 << 2),
        BTN_R_BUMPER = (1 << 3)
    };

    struct GamepadState {
        float left_x    = 0.0f; 
        float left_y    = 0.0f;
        float right_x   = 0.0f; 
        float right_y   = 0.0f;
        float trigger_l = 0.0f;
        float trigger_r = 0.0f;
        uint8_t buttons = 0;   
    };

    struct AdapterConfig {
        ControllerType type = ControllerType::NORMALIZED;
        float deadzone      = 0.3f; 
        bool invert_left_y  = false;
        bool invert_right_y = false;
    };

    LoraPayload_t adapt(const GamepadState& state, const AdapterConfig& config = {});
}


