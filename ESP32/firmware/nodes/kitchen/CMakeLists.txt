# Kitchen Node - Irene Voice Assistant
cmake_minimum_required(VERSION 3.16)

# Set node-specific variables
set(NODE_ID "kitchen")
set(FIRMWARE_VERSION "1.0.0")

# Add common firmware component
set(EXTRA_COMPONENT_DIRS "../../common")

# Include ESP-IDF
include($ENV{IDF_PATH}/tools/cmake/project.cmake)

# Project configuration
project(irene_${NODE_ID}_node) 