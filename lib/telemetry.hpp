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
} GNRMC;


GNRMC parse_raw_gps(char *raw_gps);