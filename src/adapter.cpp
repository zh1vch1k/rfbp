#include "adapter.hpp"
#include <cmath>
#include <algorithm>

namespace {

    uint8_t scale_stick(float val, float deadzone, bool invert) {
        if (invert) {
            val = -val;
        }

        if (std::abs(val) <= deadzone) {
            return 64;
        }

        val = std::clamp(val, -1.0f, 1.0f);
        int scaled = static_cast<int>(std::round((val + 1.0f) * 0.5f * 127.0f));
        return static_cast<uint8_t>(std::clamp(scaled, 0, 127));
    }

    uint8_t scale_trigger(float val, bool starts_at_minus_one) {
        float norm = val;
        if (starts_at_minus_one) {
            norm = (val + 1.0f) * 0.5f;
        }

        norm = std::clamp(norm, 0.0f, 1.0f);
        int scaled = static_cast<int>(std::round(norm * 15.0f));
        return static_cast<uint8_t>(std::clamp(scaled, 0, 15));
    }

} // namespace

namespace rfbp::adapter {

    LoraPayload_t adapt(const GamepadState& state, const AdapterConfig& config) { 
        LoraPayload_t payload = {};

        payload.st_l_ax_x = scale_stick(state.left_x, config.deadzone, false);
        payload.st_l_ax_y = scale_stick(state.left_y, config.deadzone, config.invert_left_y);
        payload.st_r_ax_x = scale_stick(state.right_x, config.deadzone, false);
        payload.st_r_ax_y = scale_stick(state.right_y, config.deadzone, config.invert_right_y);

        if (config.type == ControllerType::NORMALIZED) { 
            payload.trigger_l = scale_trigger(state.trigger_l, false);
            payload.trigger_r = scale_trigger(state.trigger_r, false);
            payload.reserved_buttons = state.buttons & 0x0F;
        }
        else if (config.type == ControllerType::DUALSENSE) { 
            payload.trigger_l = scale_trigger(state.trigger_l, true);
            payload.trigger_r = scale_trigger(state.trigger_r, true);
            payload.reserved_buttons = state.buttons & 0x0F;
        }
        else if (config.type == ControllerType::XBOX) { 
            payload.trigger_l = scale_trigger(state.trigger_l, false);
            payload.trigger_r = scale_trigger(state.trigger_r, false);
            payload.reserved_buttons = state.buttons & 0x0F;
        }
        else if (config.type == ControllerType::GENERIC) { 
            payload.trigger_l = (state.trigger_l > 0.5f) ? 15 : scale_trigger(state.trigger_l, false);
            payload.trigger_r = (state.trigger_r > 0.5f) ? 15 : scale_trigger(state.trigger_r, false);
            payload.reserved_buttons = state.buttons & 0x0F;
        }

        return payload;
    }

} // namespace rfbp::adapter