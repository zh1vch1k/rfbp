#pragma once

#include <cstdint>
#include <optional>
#include <cstdlib>
#include <cstring>
#include "speck.hpp"


typedef struct  __attribute__((__packed__)) {
    uint32_t time_utc;      
    uint32_t date_utc;     
    int32_t  latitude;     
    int32_t  longitude;     
    uint16_t speed_kmh_x10; 
    uint16_t course_deg_x10;
    uint8_t  status;        
    uint8_t  mode;       
} GNRMC_t;


typedef struct __attribute__((__packed__)){
    uint16_t bus_voltage_mv; 
    int16_t  current_ma;    
    uint8_t  power_w;       
} CompactPowerTelemetry_t;

typedef struct __attribute__((__packed__)){
    uint16_t bus_voltage_mv; 
    int16_t  current_ma;    
    uint8_t  power_w;       
} AccelerometerTelemetry_t;

typedef struct __attribute__((__packed__)) { 
    GNRMC_t gps_data;
    CompactPowerTelemetry_t power_data;
    AccelerometerTelemetry_t accelerometer_data;
} Telemetry_t;

GNRMC_t parse_raw_gps(char *raw_gps);