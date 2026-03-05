view: live_market_data {
  sql_table_name: `alti-analytics-prod.alti_analytics_prod.live_market_data` ;;

  # DIMENSIONS
  dimension: event_id {
    primary_key: yes
    type: string
    sql: GENERATE_UUID() ;; # Usually handled upstream but keeping for scaffold
  }

  dimension: event_type {
    type: string
    sql: ${TABLE}.event_type ;;
    description: "Type of telemetry event (e.g., optical_telemetry, trade)"
  }

  dimension: player_id {
    type: string
    sql: ${TABLE}.player_id ;;
  }

  dimension: team_id {
    type: string
    sql: ${TABLE}.team_id ;;
  }

  dimension_group: event {
    type: time
    timeframes: [
      raw,
      time,
      minute,
      minute10,
      hour,
      date,
      week,
      month,
      year
    ]
    sql: ${TABLE}.timestamp ;;
  }

  # BIOMETRICS
  dimension: speed_kmh {
    type: number
    sql: JSON_EXTRACT_SCALAR(${TABLE}.biometrics, '$.speed_kmh') ;;
  }

  dimension: heart_rate_bpm {
    type: number
    sql: JSON_EXTRACT_SCALAR(${TABLE}.biometrics, '$.heart_rate_bpm') ;;
    # Required for Dataplex/SOC2 integration to mask PII later
    tags: ["pii_sensitive", "medical_data"]
  }

  # MEASURES
  measure: count {
    type: count
    drill_fields: [player_id, team_id, event_time]
  }

  measure: average_heart_rate {
    type: average
    sql: ${heart_rate_bpm} ;;
    value_format_name: decimal_1
    description: "Average heart rate across the selected timeframe"
  }

  measure: max_speed {
    type: max
    sql: ${speed_kmh} ;;
    value_format_name: decimal_2
    description: "Maximum sprint speed recorded (km/h)"
  }
}

explore: live_market_data {
  label: "Alti.Analytics Real-Time Telemetry"
  description: "Explore real-time spatial and biometric workloads per player."
}
