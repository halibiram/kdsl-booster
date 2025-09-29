# Analysis of Keenetic `ensoc_dsl.ko` Kernel Module

This document outlines the findings from the reverse engineering and analysis of the `ensoc_dsl.ko` kernel module, extracted from the Keenetic KN-2112 firmware (v4.03.C.3.0-3).

## 1. Driver Identity

The kernel module identifies itself as the **NDM PTM/SAR Driver for EcoNet EN751x, v1.0.56**. This confirms it is a proprietary driver for the Lantiq/Econet EN751x series of DSL SoCs. The driver handles both PTM (VDSL) and ATM/SAR (ADSL) modes of operation.

## 2. Parameter Control Interface

The primary user-space control and monitoring interface for this driver is the `procfs` filesystem. The analysis of the module's string table and disassembly revealed the creation of numerous files under `/proc/`. This is consistent with the interaction method observed in the `src/keenetic_dsl_interface.py` HAL, which uses file-based I/O to control the hardware.

### Key `procfs` Files Identified:

The following files are created by the driver to expose statistics, debug levels, and hardware registers:

*   `/proc/qdma_status`
*   `/proc/qdma_txq`
*   `/proc/qdma_qos`
*   `/proc/qdma_tx_ratelimit`
*   `/proc/qdma_tx_qos`
*   `/proc/qdma_stats`
*   `/proc/ptm_stats`
*   `/proc/ptm_regs`
*   `/proc/ptm_regs_tpstc`
*   `/proc/ptm_debug_dmt`
*   `/proc/ptm_debug_level`
*   `/proc/sar_stats`
*   `/proc/sar_regs`
*   `/proc/sar_debug_level`

Interaction with these files (e.g., `echo <value> > /proc/ptm_debug_level`) is the intended method for manipulating the DSL line parameters from user space.

## 3. Hardware Register Mappings

The analysis provided a significant list of symbolic names for the memory-mapped hardware registers used to control the DSL chipset. The disassembly confirmed that these registers are accessed via load/store instructions to a peripheral base address in the `0xBFB00000` memory range, which is typical for MIPS SoCs.

The registers can be grouped into several functional blocks based on their prefixes:

### Frame Engine (FE) Registers

These registers control the main packet processing and DMA engine.

| Register Name        | Purpose (Inferred)                               |
| -------------------- | ------------------------------------------------ |
| `FE_DMA_GLO_CFG`     | Global DMA configuration                         |
| `FE_RST_GLO`         | Global reset control                             |
| `FE_INT_STATUS`      | Interrupt status                                 |
| `FE_INT_ENABLE`      | Interrupt enable/disable                         |
| `FE_GDM2_FWD_CFG`    | Forwarding configuration for GDM2 (PTM)          |
| `FE_GDM2_SHPR_CFG`   | Shaper/QoS configuration                         |
| `FE_GDM2_TXCHN_EN`   | Enable/disable TX channels                       |
| `FE_GDM2_RXCHN_EN`   | Enable/disable RX channels                       |

### PTM (Packet Transfer Mode) Registers

These registers are specific to the VDSL (PTM) mode of operation.

| Register Name        | Purpose (Inferred)                               |
| -------------------- | ------------------------------------------------ |
| `PTM_CTRL`           | Main PTM control register                        |
| `PTM_TX_UBUF_WR_CNT_L0` | TX buffer write count for lane 0              |
| `PTM_RMAC_PKT_CNT_P` | PTM MAC packet count                             |
| `PTM_RMAC_CRCE_CNT_P`| PTM MAC CRC error count                          |
| `TPSTC_LPBK_CFG`     | Loopback configuration                           |
| `TPSTC_TX_CFG`       | TX configuration                                 |
| `TPSTC_RX_CFG`       | RX configuration                                 |

### SAR (Segmentation and Reassembly) Registers

These registers are specific to the ADSL (ATM) mode of operation.

| Register Name        | Purpose (Inferred)                               |
| -------------------- | ------------------------------------------------ |
| `SAR_GCR`            | Global Configuration Register                    |
| `SAR_VCCR`           | Virtual Channel Configuration Register           |
| `SAR_PCR`            | Peak Cell Rate configuration                     |
| `SAR_SCR`            | Sustainable Cell Rate configuration              |
| `SAR_MPOA_GCR`       | MPOA (Multi-Protocol Over ATM) global config     |

## 4. Conclusion

The `ensoc_dsl.ko` module is a complex, proprietary driver that provides extensive control over the Lantiq/Econet DSL chipset. The analysis successfully identified the `procfs`-based control interface and a large set of symbolic hardware register names. This information is sufficient to build a user-space tool that can directly manipulate the DSL PHY layer by writing to the appropriate `/proc` files, which in turn modify the hardware registers to achieve the desired line characteristics. The findings align with the functionality implemented in the `src/` directory of the project.