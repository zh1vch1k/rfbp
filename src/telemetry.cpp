#include "speck.hpp"
#include "telemetry.hpp"


GNRMC_t parse_raw_gps(char *raw_gps) { 
    char *cursor = raw_gps;
    char *token;
    int field_idx = 0;  
    GNRMC_t data = {};

    int lat_sign = 1;
    int lon_sign = 1;

    while ((token = strsep(&cursor, ",")) != NULL) {
        if (token[0] != '\0') {
            switch (field_idx) {
                case 1:
                    data.time_utc = (uint32_t)atoi(token);
                    break;

                case 2:
                    data.status = (uint8_t)token[0];
                    break;

                case 3:
                    data.latitude = (int32_t)(atof(token) * 100000.0f + 0.5f);
                    break;

                case 4: 
                    if (token[0] == 'S') lat_sign = -1;
                    break;

                case 5:
                    data.longitude = (int32_t)(atof(token) * 100000.0f + 0.5f);
                    break;

                case 6: 
                    if (token[0] == 'W') lon_sign = -1;
                    break;

                case 7: {
                    float knots = atof(token);
                    data.speed_kmh_x10 = (uint16_t)(knots * 1.852f * 10.0f + 0.5f);
                    break;
                }

                case 8: {
                    float course = atof(token);
                    data.course_deg_x10 = (uint16_t)(course * 10.0f + 0.5f);
                    break;
                }

                case 9:
                    data.date_utc = (uint32_t)atoi(token);
                    break;

                case 12:
                    data.mode = (uint8_t)token[0];
                    break;

                default:
                    break;
            }
        }
        field_idx++;
    }

    data.latitude *= lat_sign;
    data.longitude *= lon_sign;

    if (data.status != 'A') {
        data.latitude = 0;
        data.longitude = 0;
        data.speed_kmh_x10 = 0;
        data.course_deg_x10 = 0;
    }
    return data;
}