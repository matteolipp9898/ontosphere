# Smart Building Management System -- Domain Overview

## Introduction

A **Smart Building** is an intelligent structure that uses automated processes to control the building's operations, including heating, ventilation, air conditioning (HVAC), lighting, security, and other systems. Smart buildings leverage interconnected sensors, actuators, and software platforms to optimize energy efficiency, occupant comfort, and operational performance.

## Building Structure

Every **Building** is identified by a unique name, a street address, and a total gross floor area measured in square meters. A building consists of one or more **Floors**. Each floor has a floor number, a net usable area, and a designated purpose such as office space, retail, or mechanical.

Each **Floor** contains multiple **Rooms**. A room is characterized by its room number, a human-readable name (e.g., "Conference Room A"), its area in square meters, and its maximum occupancy. Rooms are classified into types: office, meeting room, lobby, restroom, server room, or utility closet.

## Sensor Network

Rooms are equipped with various **Sensors** that continuously measure environmental conditions. Every sensor has a unique device identifier, a sensor type, a measurement unit, and a current reading value. The primary sensor types deployed across the building are:

- **Temperature Sensors** -- measure ambient air temperature in degrees Celsius. Each temperature sensor reports a `temperature` reading and is calibrated quarterly.
- **Humidity Sensors** -- measure relative humidity as a percentage. These sensors help the HVAC system maintain comfortable moisture levels.
- **Occupancy Sensors** -- detect the number of people present in a room using infrared or ultrasonic technology. They report an `occupancy` count that is used for demand-driven ventilation and lighting.
- **CO2 Sensors** -- measure carbon dioxide concentration in parts per million (ppm) to ensure adequate indoor air quality.
- **Light Sensors** -- measure ambient illuminance in lux to support automated dimming and daylight harvesting.

Each sensor is installed in exactly one room, and a room may contain multiple sensors of different types.

## HVAC System

The building's climate is managed by one or more **HVAC Systems**. An HVAC system has a model identifier, a rated capacity in kilowatts, and an operational mode (heating, cooling, ventilation, or auto). Each HVAC system serves one or more zones, where a **Zone** groups together adjacent rooms that share climate control. A zone tracks a target temperature setpoint and a current measured temperature.

An HVAC system monitors its `energy_consumption` in kilowatt-hours (kWh) and reports efficiency metrics. The system receives input from temperature and CO2 sensors within its zones to adjust airflow and temperature dynamically.

## Energy Metering

Each building has one or more **Energy Meters** that track total electrical consumption, water usage, and gas consumption. An energy meter records cumulative readings in appropriate units (kWh, liters, cubic meters) along with a timestamp. Energy meters are associated with the building as a whole or with individual floors.

## Maintenance and Alerts

When a sensor reading falls outside a predefined threshold, the system generates a **Maintenance Alert**. Each alert has a severity level (info, warning, critical), a timestamp, a description, and a resolution status (open, acknowledged, resolved). Alerts are linked to the specific sensor that triggered them and may also reference the HVAC system if the anomaly relates to climate control.

## Relationships Summary

- A **Building** *hasFloor* one or more **Floors**.
- A **Floor** *containsRoom* one or more **Rooms**.
- A **Room** *containsSensor* one or more **Sensors**.
- An **HVAC System** *servesZone* one or more **Zones**.
- A **Zone** *includesRoom* one or more **Rooms**.
- An **HVAC System** *monitorsInput* from **Sensors**.
- A **Building** *hasEnergyMeter* one or more **Energy Meters**.
- A **Floor** *hasEnergyMeter* zero or more **Energy Meters**.
- A **Sensor** *triggersAlert* zero or more **Maintenance Alerts**.
- An **HVAC System** *triggersAlert* zero or more **Maintenance Alerts**.
