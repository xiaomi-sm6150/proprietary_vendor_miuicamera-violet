#
# Copyright (C) 2023-2026 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

# Inherit from the proprietary version
include vendor/miuicamera-violet/xiaomi/BoardConfigVendor.mk

MIUICAMERA_PATH := vendor/miuicamera-violet

# Malloc
MALLOC_SVELTE := true

# Properties
TARGET_SYSTEM_PROP += $(MIUICAMERA_PATH)/system.prop

# Sepolicy
BOARD_VENDOR_SEPOLICY_DIRS += $(MIUICAMERA_PATH)/sepolicy/vendor
