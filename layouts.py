from borsh_construct import CStruct, String, U8, U16, U64, Vec, Option, Bool, Enum
from construct import Bytes, Int8ul, Int32ul, Int64ul, Padding, BitsInteger, BitsSwapped, BitStruct, Const, Flag, BytesInteger
from construct import Struct as cStruct

METADAT_STRUCTURE = CStruct(
    "instructionDiscriminator" / U8,
    "createMetadataAccountArgsV3" / CStruct(
        "data" / CStruct(
            "name" / String,
            "symbol" / String,
            "uri" / String,
            "sellerFeeBasisPoints" / U16,
            "creators" / Option(Vec(CStruct(
                "address" / Bytes(32),
                "verified" / Bool,
                "share" / U8
            ))),
            "collection" / Option(CStruct(
                "verified" / Bool,
                "key" / String
            )),
            "uses" / Option(CStruct(
                "useMethod" / Enum(
                    "Burn",
                    "Multiple",
                    "Single",
                    enum_name="UseMethod"
                ),
                "remaining" / U64,
                "total" / U64
            ))
        ),
        "isMutable" / Bool,
        "collectionDetails" / Option(String)
    )
)

POOL_INFO_LAYOUT = cStruct(
    "instruction" / Int8ul,
    "simulate_type" / Int8ul
)

SWAP_LAYOUT = cStruct(
    "instruction" / Int8ul,
    "amount_in" / Int64ul,
    "min_amount_out" / Int64ul
)

LIQ_LAYOUT = cStruct(
    "instruction" / Int8ul, 
    "amount_in" / Int64ul
)

AMM_INFO_LAYOUT_V4 = cStruct(
    'status' / Int64ul,
    'nonce' / Int64ul,
    'order_num' / Int64ul,
    'depth' / Int64ul,
    'base_decimal' / Int64ul,
    'quote_decimal' / Int64ul,
    'state' / Int64ul,
    'reset_flag' / Int64ul,
    'min_size' / Int64ul,
    'vol_max_cut_ratio' / Int64ul,
    'amount_wave_ratio' / Int64ul,
    'base_lot_size' / Int64ul,
    'quote_lot_size' / Int64ul,
    'min_price_multiplier' / Int64ul,
    'max_price_multiplier' / Int64ul,
    'system_decimal_value' / Int64ul,
    # Fees
    'min_separate_numerator' / Int64ul,
    'min_separate_denominator' / Int64ul,
    'trade_fee_numerator' / Int64ul,
    'trade_fee_denominator' / Int64ul,
    'pnl_numerator' / Int64ul,
    'pnl_denominator' / Int64ul,
    'swap_fee_numerator' / Int64ul,
    'swap_fee_denominator' / Int64ul,
    # OutPutData
    'base_need_take_pnl' / Int64ul,
    'quote_need_take_pnl' / Int64ul,
    'quote_total_pnl' / Int64ul,
    'base_total_pnl' / Int64ul,
    # 128
    'quote_total_deposited' / BytesInteger(16, signed=False, swapped=True),
    'base_total_deposited' / BytesInteger(16, signed=False, swapped=True),
    'swap_base_in_amount' / BytesInteger(16, signed=False, swapped=True),
    'swap_quote_out_amount' / BytesInteger(16, signed=False, swapped=True),

    'swap_base2_quote_fee' / Int64ul,
    # 128
    'swap_quote_in_amount' / BytesInteger(16, signed=False, swapped=True),
    'swap_base_out_amount' / BytesInteger(16, signed=False, swapped=True),

    'swap_quote2_base_fee' / Int64ul,
    # AMM Vault
    'base_vault' / Bytes(32),
    'quote_vault' / Bytes(32),
    # Mint
    'base_mint' / Bytes(32),
    'quote_mint' / Bytes(32),
    'lp_mint' / Bytes(32),
    # Market
    'open_orders' / Bytes(32),
    'market_id' / Bytes(32),
    'serum_program_id' / Bytes(32),
    'target_orders' / Bytes(32),
    'withdraw_queue' / Bytes(32),
    'lp_vault' / Bytes(32),
    'amm_owner' / Bytes(32),

    'lpReserve' / Int64ul,
)