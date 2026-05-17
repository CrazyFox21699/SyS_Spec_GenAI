// SAMPLE GOOGLE TEST STYLE REFERENCE: power_mode_gtest_sample.cpp
// Version 0.1 tool does not need to generate Google Test.
// This file is only a future style reference.

#include <gtest/gtest.h>

class PowerModeTest : public ::testing::Test {
protected:
    PowerModeInputs in {};
    PowerModeOutputs out {};
    PowerModeState state = PowerModeState::ADM1_ACC;

    void SetSignal(const char* name, int value) {
        // fake setter for style reference
    }

    void RunForMs(uint32_t ms) {
        in.T_shutdown_ms = ms;
    }
};

TEST_F(PowerModeTest, TC_PM_001_Shutdown_AllMandatory_ConditionC)
{
    // Given
    state = PowerModeState::ADM1_ACC;
    in.Mode_cmd = 1U;
    in.IGN_SW = 0U;
    in.VehicleSpeed = 0U;
    in.Battery_OK = 1U;
    in.DoorLock_STS = 0U;

    // When
    RunForMs(100U);
    state = EvaluatePowerMode(state, in, out);

    // Then
    EXPECT_EQ(state, PowerModeState::ADM1_OFF);
    EXPECT_EQ(out.Mode_STS, 0U);
    EXPECT_EQ(out.ACC_Relay, 0U);
}
