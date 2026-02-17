/*
 * Copyright (c) 2026 Kaustubh Doval
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_peripheral (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       sclk,      
    input  wire       copi,     
    input  wire       nCS,
    output reg [7:0]  en_reg_out_7_0,
    output reg [7:0]  en_reg_out_15_8,
    output reg [7:0]  en_reg_pwm_7_0,
    output reg [7:0]  en_reg_pwm_15_8,
    output reg [7:0]  pwm_duty_cycle
);
// CDC Protection (sync the signals to the clk domain)
reg [1:0] sclk_sync;
reg [1:0] copi_sync;
reg [1:0] ncs_sync;

always @(posedge clk) begin
    sclk_sync <= {sclk_sync[0], sclk};
    copi_sync <= {copi_sync[0], copi};
    ncs_sync  <= {ncs_sync[0],  nCS};
end

wire sclk_rising = (sclk_sync == 2'b01);
wire ncs_active  = (ncs_sync[1] == 1'b0);
wire ncs_rising  = (ncs_sync == 2'b01);

wire copi_s = copi_sync[1];

// Start bit counter and shift register for SPI reception

reg[15:0] shift_reg;
reg [4:0] bit_count;

reg transaction_ready;
reg transaction_processed;

// Process SPI protocol in the clk domain
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        shift_reg <= 16'd0;
        bit_count <= 5'd0;
        transaction_ready <= 1'b0;
    end else begin

        // When nCS goes high (transaction ends), validate the complete transaction
        if (ncs_active) begin
            transaction_ready <= 1'b0;

            if (sclk_rising) begin
                shift_reg <= {shift_reg[14:0], copi_s}; // Shift in the new bit
                bit_count <= bit_count + 1;
            end
        end

        // End of transaction (Write to regs)
        if (ncs_rising) begin
            if (bit_count == 16)
                transaction_ready <= 1'b1;  // Mark transaction as ready for processing
            bit_count <= 5'd0;              // Reset bit count for the next transaction
        end

        if (transaction_processed)
            transaction_ready <= 1'b0;      // Clear ready flag after processing
    end
end

// Update registers only after the complete transaction has finished and been validated
wire rw;
wire [6:0] address;
wire [7:0] data;

assign rw      = shift_reg[15];
assign address = shift_reg[14:8];
assign data    = shift_reg[7:0];

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        en_reg_out_7_0   <= 8'h00;
        en_reg_out_15_8  <= 8'h00;
        en_reg_pwm_7_0   <= 8'h00;
        en_reg_pwm_15_8  <= 8'h00;
        pwm_duty_cycle   <= 8'h00;
        transaction_processed <= 1'b0;
    
    end else if (transaction_ready && !transaction_processed) begin
        // Transaction is ready and not yet processed
        // Update the registers with the received data
        if (rw) begin
                if (address == 7'h00)
                    en_reg_out_7_0 <= data;

                else if (address == 7'h01)
                    en_reg_out_15_8 <= data;

                else if (address == 7'h02)
                    en_reg_pwm_7_0 <= data;

                else if (address == 7'h03)
                    en_reg_pwm_15_8 <= data;

                else if (address == 7'h04)
                    pwm_duty_cycle <= data;

                // invalid addresses ignored
            end

        // Set the processed flag
        transaction_processed <= 1'b1;
    
    end else if (!transaction_ready && transaction_processed) begin
        // Reset processed flag when ready flag is cleared
        transaction_processed <= 1'b0;
    end
end


endmodule