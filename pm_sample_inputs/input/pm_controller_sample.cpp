// SAMPLE SOURCE CODE: pm_controller_sample.cpp
// Fake implementation-style input for Power Mode Test Spec Assistant.
// Purpose: provide signal names, state names, and output API style.

#include <cstdint>

enum class PowerModeState {
    ADM1_OFF,
    ADM1_ACC,
    TRANS_SHUTDOWN,
    FAIL_SAFE
};

struct PowerModeInputs {
    uint8_t Mode_cmd;       // 0=no request, 1=shutdown request, 2=ACC request
    uint8_t IGN_SW;         // 0=OFF, 1=ON
    uint16_t VehicleSpeed;  // km/h
    uint8_t Battery_OK;     // 0=abnormal, 1=normal
    uint8_t DoorLock_STS;   // 0=unlocked, 1=locked
    uint32_t T_shutdown_ms;
    uint32_t T_trans_ms;
};

struct PowerModeOutputs {
    uint8_t Mode_STS;    // 0=OFF, 1=ACC
    uint8_t ACC_Relay;   // 0=OFF, 1=ON
};

bool Condition_E(const PowerModeInputs& in) {
    return (in.Mode_cmd == 1U) && (in.T_shutdown_ms >= 100U);
}

bool Condition_A(const PowerModeInputs& in) {
    return in.IGN_SW == 0U;
}

bool Condition_B(const PowerModeInputs& in) {
    return in.VehicleSpeed == 0U;
}

bool Condition_C(const PowerModeInputs& in) {
    return in.Battery_OK == 1U;
}

bool Condition_D(const PowerModeInputs& in) {
    return in.DoorLock_STS == 1U;
}

PowerModeState EvaluatePowerMode(
    PowerModeState current,
    const PowerModeInputs& in,
    PowerModeOutputs& out)
{
    if (current == PowerModeState::ADM1_ACC) {
        if (Condition_E(in) && Condition_A(in) && Condition_B(in) &&
            (Condition_C(in) || Condition_D(in))) {
            out.Mode_STS = 0U;
            out.ACC_Relay = 0U;
            return PowerModeState::ADM1_OFF;
        }

        if ((in.Battery_OK == 0U) || (in.T_trans_ms > 1000U)) {
            out.Mode_STS = 0U;
            out.ACC_Relay = 0U;
            return PowerModeState::FAIL_SAFE;
        }
    }

    return current;
}
