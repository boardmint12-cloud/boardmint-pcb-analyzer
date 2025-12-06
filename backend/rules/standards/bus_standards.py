"""
Communication Bus Standards
I2C, SPI, RS-485, CAN Bus design rules and calculations

Sources:
- AN10216 I2C Manual (NXP/Philips)
- TI SLLA272B RS-485 Design Guide
- 3peak/ON Semi CAN Bus Application Notes
Reference: /Users/pranavchahal/Downloads/extracted_content-1/COMPILED_ALL_PDFS.txt
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Tuple, List
import math


class I2CSpeed(str, Enum):
    """I2C Bus Speed Modes"""
    STANDARD = "standard"     # 100 kHz
    FAST = "fast"             # 400 kHz
    FAST_PLUS = "fast_plus"   # 1 MHz
    HIGH_SPEED = "high_speed" # 3.4 MHz


class CANSpeed(str, Enum):
    """CAN Bus Speed Classes"""
    LOW_SPEED = "low_speed"       # Up to 125 kbps
    HIGH_SPEED = "high_speed"     # Up to 1 Mbps
    CAN_FD = "can_fd"             # Up to 5 Mbps


@dataclass
class I2CParameters:
    """I2C Bus Parameters"""
    speed_mode: I2CSpeed
    max_frequency_hz: int
    max_bus_capacitance_pf: int
    min_pull_up_ohm: float
    max_pull_up_ohm: float
    max_rise_time_ns: int
    max_fall_time_ns: int
    vdd_v: float


@dataclass
class RS485Parameters:
    """RS-485 Bus Parameters"""
    termination_ohm: float
    failsafe_bias_high_ohm: float
    failsafe_bias_low_ohm: float
    max_nodes: int
    max_bus_length_m: float
    max_data_rate_bps: int


@dataclass
class CANParameters:
    """CAN Bus Parameters"""
    termination_ohm: float
    differential_impedance_ohm: float
    max_nodes: int
    max_bus_length_m: float
    data_rate_bps: int


class BusStandards:
    """
    Communication Bus Standards Reference
    
    Contains design rules, calculations, and validation for:
    - I2C (including SMBus)
    - SPI
    - RS-485
    - CAN Bus
    """
    
    # ==========================================================================
    # I2C BUS PARAMETERS (from AN10216)
    # ==========================================================================
    
    I2C_SPECS: Dict[I2CSpeed, I2CParameters] = {
        I2CSpeed.STANDARD: I2CParameters(
            speed_mode=I2CSpeed.STANDARD,
            max_frequency_hz=100000,
            max_bus_capacitance_pf=400,
            min_pull_up_ohm=1000,     # Based on 3mA sink, VOL=0.4V
            max_pull_up_ohm=10000,    # Based on rise time
            max_rise_time_ns=1000,
            max_fall_time_ns=300,
            vdd_v=5.0
        ),
        I2CSpeed.FAST: I2CParameters(
            speed_mode=I2CSpeed.FAST,
            max_frequency_hz=400000,
            max_bus_capacitance_pf=400,
            min_pull_up_ohm=1000,
            max_pull_up_ohm=4700,     # Tighter for faster rise time
            max_rise_time_ns=300,
            max_fall_time_ns=300,
            vdd_v=5.0
        ),
        I2CSpeed.FAST_PLUS: I2CParameters(
            speed_mode=I2CSpeed.FAST_PLUS,
            max_frequency_hz=1000000,
            max_bus_capacitance_pf=550,  # Increased drive capability
            min_pull_up_ohm=500,
            max_pull_up_ohm=2200,
            max_rise_time_ns=120,
            max_fall_time_ns=120,
            vdd_v=3.3
        ),
        I2CSpeed.HIGH_SPEED: I2CParameters(
            speed_mode=I2CSpeed.HIGH_SPEED,
            max_frequency_hz=3400000,
            max_bus_capacitance_pf=100,  # Very limited
            min_pull_up_ohm=300,
            max_pull_up_ohm=1000,
            max_rise_time_ns=40,
            max_fall_time_ns=40,
            vdd_v=3.3
        ),
    }
    
    # ==========================================================================
    # RS-485 BUS PARAMETERS (from TI SLLA272B)
    # ==========================================================================
    
    RS485_SPEC = RS485Parameters(
        termination_ohm=120.0,           # Standard line impedance
        failsafe_bias_high_ohm=560.0,    # Pull-up on A (D+)
        failsafe_bias_low_ohm=560.0,     # Pull-down on B (D-)
        max_nodes=32,                     # Standard driver load units
        max_bus_length_m=1200.0,         # At 100kbps
        max_data_rate_bps=10000000       # 10 Mbps max
    )
    
    # RS-485 Data Rate vs Bus Length (from TI app note)
    RS485_RATE_VS_LENGTH: Dict[int, float] = {
        # Data rate (bps): Max length (m)
        100000: 1200,
        500000: 300,
        1000000: 150,
        2500000: 60,
        5000000: 30,
        10000000: 15,
    }
    
    # ==========================================================================
    # CAN BUS PARAMETERS
    # ==========================================================================
    
    CAN_SPECS: Dict[CANSpeed, CANParameters] = {
        CANSpeed.LOW_SPEED: CANParameters(
            termination_ohm=120.0,
            differential_impedance_ohm=120.0,
            max_nodes=32,
            max_bus_length_m=1000.0,
            data_rate_bps=125000
        ),
        CANSpeed.HIGH_SPEED: CANParameters(
            termination_ohm=120.0,
            differential_impedance_ohm=120.0,
            max_nodes=32,
            max_bus_length_m=40.0,       # At 1Mbps
            data_rate_bps=1000000
        ),
        CANSpeed.CAN_FD: CANParameters(
            termination_ohm=120.0,
            differential_impedance_ohm=120.0,
            max_nodes=32,
            max_bus_length_m=15.0,       # At 5Mbps
            data_rate_bps=5000000
        ),
    }
    
    # CAN Data Rate vs Bus Length
    CAN_RATE_VS_LENGTH: Dict[int, float] = {
        # Data rate (bps): Max length (m)
        125000: 500,
        250000: 250,
        500000: 100,
        1000000: 40,
        2000000: 20,
        5000000: 10,
    }
    
    # ==========================================================================
    # SPI BUS PARAMETERS
    # ==========================================================================
    
    SPI_MAX_FREQUENCY_HZ = 50000000  # 50 MHz typical max
    SPI_MAX_TRACE_LENGTH_MM = 150    # 15cm max for high-speed SPI
    
    # ==========================================================================
    # I2C CALCULATIONS (from AN10216 Pull-up Resistor Calculation)
    # ==========================================================================
    
    @classmethod
    def calculate_i2c_pull_up(
        cls,
        vdd_v: float,
        bus_capacitance_pf: float,
        speed_mode: I2CSpeed = I2CSpeed.FAST,
        vol_max_v: float = 0.4,
        sink_current_ma: float = 3.0
    ) -> Tuple[float, float, Dict]:
        """
        Calculate I2C pull-up resistor range
        
        Formula from AN10216:
        - Rp(min) = (VDD - VOL_max) / IOL (sink current)
        - Rp(max) = tr / (0.8473 * Cb) where tr = max rise time
        
        Args:
            vdd_v: Supply voltage
            bus_capacitance_pf: Total bus capacitance
            speed_mode: I2C speed mode
            vol_max_v: Maximum low output voltage
            sink_current_ma: Output sink current capability
        
        Returns:
            Tuple of (min_rp_ohm, max_rp_ohm, details)
        """
        spec = cls.I2C_SPECS.get(speed_mode, cls.I2C_SPECS[I2CSpeed.FAST])
        
        # Minimum pull-up (DC approach - sink current limit)
        # Rp_min = (VDD - VOL) / IOL
        rp_min = (vdd_v - vol_max_v) / (sink_current_ma / 1000)
        
        # Maximum pull-up (AC approach - rise time limit)
        # Rise time equation: tr = 0.8473 * Rp * Cb
        # Rp_max = tr / (0.8473 * Cb)
        rise_time_s = spec.max_rise_time_ns * 1e-9
        bus_capacitance_f = bus_capacitance_pf * 1e-12
        rp_max = rise_time_s / (0.8473 * bus_capacitance_f)
        
        # Clamp to spec limits
        rp_min = max(rp_min, spec.min_pull_up_ohm)
        rp_max = min(rp_max, spec.max_pull_up_ohm)
        
        # Check if valid range exists
        if rp_min > rp_max:
            # Bus capacitance too high - need active pull-up or slower speed
            pass
        
        # Recommend middle of range
        rp_recommended = math.sqrt(rp_min * rp_max)  # Geometric mean
        
        details = {
            "vdd_v": vdd_v,
            "bus_capacitance_pf": bus_capacitance_pf,
            "speed_mode": speed_mode.value,
            "max_rise_time_ns": spec.max_rise_time_ns,
            "sink_current_ma": sink_current_ma,
            "rp_min_ohm": round(rp_min),
            "rp_max_ohm": round(rp_max),
            "rp_recommended_ohm": round(rp_recommended),
            "valid_range": rp_min <= rp_max,
        }
        
        return (round(rp_min), round(rp_max), details)
    
    @classmethod
    def validate_i2c_bus(
        cls,
        pull_up_ohm: float,
        bus_capacitance_pf: float,
        vdd_v: float,
        speed_mode: I2CSpeed
    ) -> Tuple[bool, List[str]]:
        """
        Validate I2C bus design
        
        Args:
            pull_up_ohm: Pull-up resistor value
            bus_capacitance_pf: Total bus capacitance
            vdd_v: Supply voltage
            speed_mode: Target speed mode
        
        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []
        spec = cls.I2C_SPECS.get(speed_mode, cls.I2C_SPECS[I2CSpeed.FAST])
        
        # Check bus capacitance
        if bus_capacitance_pf > spec.max_bus_capacitance_pf:
            issues.append(
                f"Bus capacitance {bus_capacitance_pf}pF exceeds max {spec.max_bus_capacitance_pf}pF "
                f"for {speed_mode.value} mode"
            )
        
        # Calculate valid pull-up range
        rp_min, rp_max, _ = cls.calculate_i2c_pull_up(
            vdd_v, bus_capacitance_pf, speed_mode
        )
        
        if pull_up_ohm < rp_min:
            issues.append(
                f"Pull-up {pull_up_ohm}Ω too low (min {rp_min}Ω). "
                f"May exceed device sink current capacity."
            )
        
        if pull_up_ohm > rp_max:
            issues.append(
                f"Pull-up {pull_up_ohm}Ω too high (max {rp_max}Ω). "
                f"Rise time will exceed {spec.max_rise_time_ns}ns spec."
            )
        
        return (len(issues) == 0, issues)
    
    # ==========================================================================
    # RS-485 VALIDATION
    # ==========================================================================
    
    @classmethod
    def validate_rs485_bus(
        cls,
        has_termination: bool,
        termination_ohm: float,
        has_failsafe_bias: bool,
        node_count: int,
        bus_length_m: float,
        data_rate_bps: int
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate RS-485 bus design
        
        Args:
            has_termination: Whether termination resistor present
            termination_ohm: Termination resistor value
            has_failsafe_bias: Whether failsafe biasing present
            node_count: Number of nodes on bus
            bus_length_m: Bus length in meters
            data_rate_bps: Data rate in bps
        
        Returns:
            Tuple of (is_valid, critical_issues, warnings)
        """
        critical = []
        warnings = []
        
        # Check termination
        if not has_termination:
            critical.append(
                "Missing 120Ω termination resistor between A and B lines. "
                "Signal reflections will cause communication errors."
            )
        elif abs(termination_ohm - 120) > 12:  # 10% tolerance
            warnings.append(
                f"Termination resistor {termination_ohm}Ω differs from standard 120Ω. "
                f"Use 120Ω ±10% for proper impedance matching."
            )
        
        # Check node count
        if node_count > cls.RS485_SPEC.max_nodes:
            critical.append(
                f"Node count {node_count} exceeds RS-485 limit of {cls.RS485_SPEC.max_nodes}. "
                f"Use repeaters or high-unit-load transceivers."
            )
        
        # Check bus length vs data rate
        max_length = cls.RS485_RATE_VS_LENGTH.get(data_rate_bps)
        if max_length is None:
            # Interpolate
            for rate, length in sorted(cls.RS485_RATE_VS_LENGTH.items()):
                if rate >= data_rate_bps:
                    max_length = length
                    break
        
        if max_length and bus_length_m > max_length:
            critical.append(
                f"Bus length {bus_length_m}m exceeds maximum {max_length}m "
                f"for {data_rate_bps/1000:.0f}kbps data rate."
            )
        
        # Check failsafe biasing
        if not has_failsafe_bias:
            warnings.append(
                "No failsafe biasing detected. Add 560Ω pull-up on A, "
                "pull-down on B to ensure known idle state."
            )
        
        return (len(critical) == 0, critical, warnings)
    
    # ==========================================================================
    # CAN BUS VALIDATION
    # ==========================================================================
    
    @classmethod
    def validate_can_bus(
        cls,
        has_termination: bool,
        termination_ohm: float,
        node_count: int,
        bus_length_m: float,
        data_rate_bps: int
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate CAN bus design
        
        Args:
            has_termination: Whether termination present
            termination_ohm: Termination value
            node_count: Number of nodes
            bus_length_m: Bus length
            data_rate_bps: Data rate
        
        Returns:
            Tuple of (is_valid, critical_issues, warnings)
        """
        critical = []
        warnings = []
        
        # Check termination
        if not has_termination:
            critical.append(
                "Missing 120Ω termination between CANH and CANL. "
                "Bus requires termination at both ends."
            )
        elif abs(termination_ohm - 120) > 12:
            warnings.append(
                f"Termination {termination_ohm}Ω differs from standard 120Ω."
            )
        
        # Check bus length vs data rate
        max_length = cls.CAN_RATE_VS_LENGTH.get(data_rate_bps)
        if max_length is None:
            for rate, length in sorted(cls.CAN_RATE_VS_LENGTH.items()):
                if rate >= data_rate_bps:
                    max_length = length
                    break
        
        if max_length and bus_length_m > max_length:
            critical.append(
                f"Bus length {bus_length_m}m exceeds max {max_length}m "
                f"for {data_rate_bps/1000:.0f}kbps."
            )
        
        return (len(critical) == 0, critical, warnings)
    
    # ==========================================================================
    # SPI VALIDATION
    # ==========================================================================
    
    @classmethod
    def validate_spi_layout(
        cls,
        trace_length_mm: float,
        frequency_hz: int,
        has_series_resistor: bool = False
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate SPI layout
        
        Args:
            trace_length_mm: SPI signal trace length
            frequency_hz: SPI clock frequency
            has_series_resistor: Whether series termination present
        
        Returns:
            Tuple of (is_valid, critical_issues, warnings)
        """
        critical = []
        warnings = []
        
        # Calculate max trace length based on frequency
        # Rule of thumb: trace length < λ/10 for transmission line effects
        # λ = c / (f * sqrt(Er)), Er ≈ 4 for FR4
        c = 3e8  # Speed of light
        er = 4.0
        wavelength_m = c / (frequency_hz * math.sqrt(er))
        max_length_m = wavelength_m / 10
        max_length_mm = max_length_m * 1000
        
        if trace_length_mm > max_length_mm:
            critical.append(
                f"SPI trace {trace_length_mm}mm exceeds λ/10 = {max_length_mm:.0f}mm "
                f"at {frequency_hz/1e6:.0f}MHz. Transmission line effects will degrade signal."
            )
        
        # High-speed SPI recommendations
        if frequency_hz > 10e6:
            if not has_series_resistor:
                warnings.append(
                    f"SPI at {frequency_hz/1e6:.0f}MHz: Consider 22-33Ω series resistors "
                    f"on MOSI/CLK near source for signal integrity."
                )
        
        # Check absolute max
        if trace_length_mm > cls.SPI_MAX_TRACE_LENGTH_MM:
            warnings.append(
                f"SPI trace {trace_length_mm}mm exceeds recommended {cls.SPI_MAX_TRACE_LENGTH_MM}mm max. "
                f"Consider reducing clock speed or adding buffering."
            )
        
        return (len(critical) == 0, critical, warnings)
    
    @classmethod
    def get_decoupling_recommendations(
        cls,
        bus_type: str,
        voltage_v: float
    ) -> Dict:
        """
        Get decoupling capacitor recommendations for bus interfaces
        
        Args:
            bus_type: "i2c", "spi", "rs485", "can"
            voltage_v: Supply voltage
        
        Returns:
            Dict with recommendations
        """
        recommendations = {
            "i2c": {
                "bulk": "10µF electrolytic or ceramic",
                "bypass": "100nF ceramic (X7R) per device",
                "placement": "Within 3mm of VCC pin",
                "notes": "Critical for noise immunity at higher speeds"
            },
            "spi": {
                "bulk": "10µF ceramic",
                "bypass": "100nF ceramic per device, 10nF for high-speed",
                "placement": "Adjacent to IC, short traces to GND",
                "notes": "Add 100pF on CLK for EMI reduction"
            },
            "rs485": {
                "bulk": "100µF at connector",
                "bypass": "100nF ceramic at transceiver VCC",
                "placement": "Transceiver VCC to GND, short loop",
                "notes": "Add TVS diodes at connector for ESD"
            },
            "can": {
                "bulk": "10-100µF at transceiver",
                "bypass": "100nF ceramic + 10nF ceramic",
                "placement": "Close to transceiver power pins",
                "notes": "Separate analog and digital grounds under IC"
            },
        }
        
        return recommendations.get(bus_type.lower(), recommendations["spi"])
