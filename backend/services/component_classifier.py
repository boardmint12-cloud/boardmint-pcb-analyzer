"""
Component Classification - Deterministic component type identification

CRITICAL FIX: This prevents AI from misidentifying components.

Before this fix, the AI would see a flat list like:
  U1: ATmega328P-PU
  U2: NRF24L01
  U3: LP2985-3.3

And it would sometimes pick NRF24L01 as the "main MCU" because:
- It has prominent numbers (24, 01)
- No explicit rules told it ATmega328P is the actual CPU

This classifier provides DETERMINISTIC ground truth that the AI
MUST respect, preventing misidentification bugs.
"""
from typing import Dict, Any, List, Optional
from parsers.base_parser import Component
import logging

logger = logging.getLogger(__name__)


class ComponentClassifier:
    """
    Deterministic component classifier using pattern matching.
    
    Returns component types that AI analysis MUST respect.
    """
    
    # MCU/Microcontroller patterns
    MCU_PATTERNS = [
        'atmega', 'attiny', 'atxmega',  # Atmel/Microchip AVR
        'stm32', 'stm8',                 # STMicroelectronics
        'pic16', 'pic18', 'pic24', 'pic32',  # Microchip PIC
        'esp32', 'esp8266',              # Espressif (when used as MCU, not module)
        'nrf52', 'nrf51',                # Nordic (MCU chips, not NRF24)
        'msp430', 'msp432',              # TI MSP430
        'sam3', 'sam4', 'samd',          # Atmel/Microchip SAM
        'lpc',                           # NXP LPC
        'kinetis',                       # NXP Kinetis
        'rp2040',                        # Raspberry Pi Pico
        'ch32',                          # WCH RISC-V
        'gd32',                          # GigaDevice
        'at89', 'at90',                  # Atmel 8051/AVR
    ]
    
    # Wireless/Radio modules (NOT main CPUs)
    WIRELESS_PATTERNS = [
        'nrf24',                         # Nordic NRF24L01 radio
        'cc1101', 'cc2500',              # TI radio chips
        'sx127', 'sx126',                # Semtech LoRa
        'rfm', 'rfm69', 'rfm95',         # HopeRF modules
        'hc-05', 'hc-06',                # Bluetooth modules
        'esp-01', 'esp-12',              # ESP8266 as module (not bare chip)
        'bluetooth', 'wifi', 'lora', 'zigbee',
        'bt', 'ble',
    ]
    
    # Voltage regulators and power management
    REGULATOR_PATTERNS = [
        'lm78', 'lm79',                  # Linear regulators (78xx, 79xx)
        'lm1117', 'ams1117',             # LDOs
        'lp2985', 'lp5907',              # TI LDOs
        'ldo', 'regulator',
        'buck', 'boost',                 # DC-DC converters
        'mp1584', 'mp2307',              # Switching regulators
        'tps', 'tlv',                    # TI power chips
        'ap', 'xc6',                     # Other LDO families
        'mcp1700', 'mcp1703',            # Microchip LDOs
    ]
    
    # Sensors
    SENSOR_PATTERNS = [
        'bme280', 'bmp280', 'bmp180',    # Pressure/humidity sensors
        'dht11', 'dht22', 'am2302',      # Temp/humidity sensors
        'hx711',                         # Load cell amp
        'mpu6050', 'mpu9250',            # IMU/accelerometer
        'ads1115', 'ads1015',            # ADCs
        'tmp', 'lm35', 'ds18',           # Temperature sensors
        'hmc5883', 'qmc5883',            # Magnetometers
        'veml', 'tsl',                   # Light sensors
        'sensor',
    ]
    
    # Memory chips
    MEMORY_PATTERNS = [
        '24c', '24lc',                   # I2C EEPROM
        'at24', 'at25',                  # Atmel EEPROM
        'w25', 'mx25',                   # SPI Flash
        'sram', 'fram', 'eeprom', 'flash',
    ]
    
    # Communication interfaces
    COMM_PATTERNS = [
        'ch340', 'cp2102', 'ft232',      # USB-UART bridges
        'max3232', 'max485',             # RS232/RS485
        'can', 'mcp2515',                # CAN controllers
    ]
    
    # Display drivers
    DISPLAY_PATTERNS = [
        'ssd1306', 'sh1106',             # OLED drivers
        'st7735', 'st7789', 'ili9341',   # TFT drivers
        'lcd', 'oled', 'tft',
    ]
    
    def classify_component(self, component: Component) -> str:
        """
        Classify a component into a type category.
        
        Returns one of:
        - 'MCU' - Microcontroller/main processor
        - 'WIRELESS_MODULE' - Radio/wireless module
        - 'VOLTAGE_REGULATOR' - Power management
        - 'SENSOR' - Sensor or ADC
        - 'MEMORY' - EEPROM, Flash, SRAM
        - 'COMMUNICATION' - UART, CAN, RS485 interface
        - 'DISPLAY' - LCD/OLED driver
        - 'CONNECTOR' - Physical connector
        - 'PASSIVE' - Resistor, capacitor, inductor
        - 'OTHER' - Unknown/generic IC
        """
        value = (component.value or "").lower()
        footprint = (component.footprint or "").lower()
        ref = (component.reference or "").upper()
        
        # Passives - check reference first
        if ref and ref[0] in ('R', 'C', 'L', 'D', 'Q'):
            return 'PASSIVE'
        
        # Connectors
        if ref.startswith('J') or ref.startswith('P'):
            return 'CONNECTOR'
        
        if any(k in footprint for k in ['connector', 'header', 'usb', 'jst', 'terminal']):
            return 'CONNECTOR'
        
        # MCUs - HIGHEST PRIORITY (check before wireless to avoid ESP32 confusion)
        if any(pattern in value for pattern in self.MCU_PATTERNS):
            # But exclude NRF24 which contains "nrf" but is not an MCU
            if 'nrf24' not in value:
                return 'MCU'
        
        # Wireless modules (NOT MCUs)
        if any(pattern in value for pattern in self.WIRELESS_PATTERNS):
            return 'WIRELESS_MODULE'
        
        # Voltage regulators
        if any(pattern in value for pattern in self.REGULATOR_PATTERNS):
            return 'VOLTAGE_REGULATOR'
        
        # Sensors
        if any(pattern in value for pattern in self.SENSOR_PATTERNS):
            return 'SENSOR'
        
        # Memory
        if any(pattern in value for pattern in self.MEMORY_PATTERNS):
            return 'MEMORY'
        
        # Communication interfaces
        if any(pattern in value for pattern in self.COMM_PATTERNS):
            return 'COMMUNICATION'
        
        # Display drivers
        if any(pattern in value for pattern in self.DISPLAY_PATTERNS):
            return 'DISPLAY'
        
        # Unknown IC
        return 'OTHER'
    
    def classify_all(self, components: List[Component]) -> List[Dict[str, Any]]:
        """
        Classify all components and return enriched data.
        
        Returns list of dicts with: ref, value, footprint, class, x, y
        """
        classified = []
        
        for comp in components:
            comp_class = self.classify_component(comp)
            
            classified.append({
                'ref': comp.reference,
                'value': comp.value,
                'footprint': comp.footprint,
                'class': comp_class,
                'x': comp.x,
                'y': comp.y,
                'rotation': comp.rotation,
                'layer': comp.layer,
            })
        
        return classified
    
    def find_main_mcu(self, classified_components: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Find the main microcontroller from classified components.
        
        Rules:
        1. Must have class == 'MCU'
        2. If multiple MCUs, prefer:
           - Larger footprint (more capable chip)
           - Non-Tiny variants (ATmega > ATtiny)
           - First occurrence if still tied
        """
        mcus = [c for c in classified_components if c['class'] == 'MCU']
        
        if len(mcus) == 0:
            logger.info("No MCU found in design")
            return None
        
        if len(mcus) == 1:
            logger.info(f"Main MCU identified: {mcus[0]['ref']} - {mcus[0]['value']}")
            return mcus[0]
        
        # Multiple MCUs - need to pick the "main" one
        logger.info(f"Multiple MCUs found: {[m['ref'] for m in mcus]}")
        
        # Prefer non-Tiny variants
        non_tiny = [m for m in mcus if 'tiny' not in m['value'].lower()]
        if len(non_tiny) == 1:
            logger.info(f"Main MCU (non-Tiny): {non_tiny[0]['ref']}")
            return non_tiny[0]
        
        # Otherwise just take first
        logger.info(f"Main MCU (first found): {mcus[0]['ref']}")
        return mcus[0]
    
    def group_by_type(self, classified_components: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group classified components by type.
        
        Returns: {'MCU': [...], 'WIRELESS_MODULE': [...], ...}
        """
        groups: Dict[str, List[Dict[str, Any]]] = {}
        
        for comp in classified_components:
            comp_class = comp['class']
            if comp_class not in groups:
                groups[comp_class] = []
            groups[comp_class].append(comp)
        
        return groups
