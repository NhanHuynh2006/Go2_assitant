#!/usr/bin/env bash
# ============================================================
#  export_gguf.sh — <merged_dir> (HF) -> GGUF Q4_K_M cho llama.cpp
#  Cach dung:
#    bash export_gguf.sh                                  # mac dinh merged_1.5b
#    bash export_gguf.sh merged_0.5b govoice-qwen2.5-0.5b # ban 0.5B
# ============================================================
set -e

# llama.cpp: dat LLAMA=... neu khong o ~/llama.cpp (vd ../NhanHuynh/go2_jetson_demo/llama.cpp)
LLAMA=${LLAMA:-~/llama.cpp}
QUANT=$(ls $LLAMA/build-cuda/bin/llama-quantize $LLAMA/build/bin/llama-quantize 2>/dev/null | head -1)
MERGED=${1:-merged_1.5b}
NAME=${2:-govoice-qwen2.5-1.5b}

echo "[1/3] Cai phu thuoc converter (1 lan)..."
python3 -c "import gguf" 2>/dev/null || pip install -q gguf sentencepiece protobuf

echo "[2/3] Convert $MERGED -> GGUF f16..."
python3 $LLAMA/convert_hf_to_gguf.py $MERGED --outfile ${NAME}-f16.gguf

echo "[3/3] Quantize Q4_K_M..."
$QUANT ${NAME}-f16.gguf ${NAME}-q4_k_m.gguf Q4_K_M
rm -f ${NAME}-f16.gguf

echo ""
echo "XONG! Model: $(pwd)/${NAME}-q4_k_m.gguf"
echo "Chay thu:"
echo "  ~/llama.cpp/build/bin/llama-server -m $(pwd)/${NAME}-q4_k_m.gguf -ngl 99 -c 2048 --port 8080"
