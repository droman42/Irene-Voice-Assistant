#!/bin/bash
"""
Wake Word Model Training Script

Trains a microWakeWord "medium-12-bn" model using the collected audio data.
Based on ESP32 firmware specification.

Usage:
    ./train_model.sh jarvis
    ./train_model.sh jarvis --epochs 60 --batch_size 32
"""

set -e  # Exit on any error

# Default parameters from firmware spec
WAKE_WORD=""
EPOCHS=55
BATCH_SIZE=16
MODEL_SIZE="medium"
SAMPLE_RATE=16000
USE_BATCH_NORM=true
LEARNING_RATE=0.001

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/data"
MODELS_DIR="$PROJECT_DIR/models"
CONFIGS_DIR="$PROJECT_DIR/configs"

function usage() {
    echo "Usage: $0 <wake_word> [options]"
    echo ""
    echo "Arguments:"
    echo "  wake_word          Wake word to train (e.g., 'jarvis')"
    echo ""
    echo "Options:"
    echo "  --epochs N         Number of training epochs (default: 55)"
    echo "  --batch_size N     Batch size for training (default: 16)"
    echo "  --learning_rate F  Learning rate (default: 0.001)"
    echo "  --no_batch_norm    Disable batch normalization"
    echo "  --help            Show this help"
    echo ""
    echo "Example:"
    echo "  $0 jarvis --epochs 60 --batch_size 32"
    exit 1
}

function check_data() {
    echo "🔍 Checking training data..."
    
    if [[ ! -d "$DATA_DIR/positive" ]]; then
        echo "❌ Error: No positive samples directory found at $DATA_DIR/positive"
        exit 1
    fi
    
    if [[ ! -d "$DATA_DIR/negative" ]]; then
        echo "❌ Error: No negative samples directory found at $DATA_DIR/negative"
        exit 1
    fi
    
    # Count positive samples
    POSITIVE_COUNT=$(find "$DATA_DIR/positive" -name "*.wav" | wc -l)
    if [[ $POSITIVE_COUNT -lt 200 ]]; then
        echo "⚠️  Warning: Only $POSITIVE_COUNT positive samples found (recommended: ≥200)"
        echo "   This may result in poor model performance."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo "✅ Found $POSITIVE_COUNT positive samples"
    fi
    
    # Count speakers
    SPEAKER_COUNT=$(find "$DATA_DIR/positive" -maxdepth 1 -type d | tail -n +2 | wc -l)
    if [[ $SPEAKER_COUNT -lt 4 ]]; then
        echo "⚠️  Warning: Only $SPEAKER_COUNT speakers found (recommended: ≥4)"
        echo "   This may reduce model generalization."
    else
        echo "✅ Found $SPEAKER_COUNT speakers"
    fi
    
    # Check negative samples
    NEGATIVE_FILES=$(find "$DATA_DIR/negative" -name "*.wav" | wc -l)
    if [[ $NEGATIVE_FILES -eq 0 ]]; then
        echo "❌ Error: No negative samples found"
        exit 1
    else
        echo "✅ Found $NEGATIVE_FILES negative sample files"
    fi
    
    echo ""
}

function prepare_training() {
    echo "📁 Preparing training environment..."
    
    # Create output directories
    mkdir -p "$MODELS_DIR"
    mkdir -p "$CONFIGS_DIR"
    
    # Create timestamp for this training run
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    MODEL_OUTPUT="$MODELS_DIR/${WAKE_WORD}_${MODEL_SIZE}_${TIMESTAMP}.tflite"
    LOG_FILE="$MODELS_DIR/${WAKE_WORD}_${MODEL_SIZE}_${TIMESTAMP}.log"
    
    echo "📝 Model will be saved to: $MODEL_OUTPUT"
    echo "📋 Training log will be saved to: $LOG_FILE"
    echo ""
}

function train_model() {
    echo "🚀 Starting model training..."
    echo "Wake word: $WAKE_WORD"
    echo "Model size: $MODEL_SIZE"
    echo "Epochs: $EPOCHS"
    echo "Batch size: $BATCH_SIZE"
    echo "Learning rate: $LEARNING_RATE"
    echo "Batch normalization: $USE_BATCH_NORM"
    echo ""
    
    # Build microwakeword-train command
    TRAIN_CMD="microwakeword-train"
    TRAIN_CMD="$TRAIN_CMD --wake_word \"$WAKE_WORD\""
    TRAIN_CMD="$TRAIN_CMD --positive_dir \"$DATA_DIR/positive\""
    TRAIN_CMD="$TRAIN_CMD --negative_dir \"$DATA_DIR/negative\""
    TRAIN_CMD="$TRAIN_CMD --model_size $MODEL_SIZE"
    TRAIN_CMD="$TRAIN_CMD --epochs $EPOCHS"
    TRAIN_CMD="$TRAIN_CMD --batch_size $BATCH_SIZE"
    TRAIN_CMD="$TRAIN_CMD --learning_rate $LEARNING_RATE"
    TRAIN_CMD="$TRAIN_CMD --sample_rate $SAMPLE_RATE"
    TRAIN_CMD="$TRAIN_CMD --output \"$MODEL_OUTPUT\""
    
    if [[ "$USE_BATCH_NORM" == "true" ]]; then
        TRAIN_CMD="$TRAIN_CMD --batch_norm"
    fi
    
    # Save training configuration
    CONFIG_FILE="$CONFIGS_DIR/${WAKE_WORD}_${MODEL_SIZE}_${TIMESTAMP}.yaml"
    cat > "$CONFIG_FILE" << EOF
# Training Configuration - $TIMESTAMP
wake_word: "$WAKE_WORD"
model_size: "$MODEL_SIZE"
epochs: $EPOCHS
batch_size: $BATCH_SIZE
learning_rate: $LEARNING_RATE
sample_rate: $SAMPLE_RATE
batch_norm: $USE_BATCH_NORM
positive_dir: "$DATA_DIR/positive"
negative_dir: "$DATA_DIR/negative"
output_model: "$MODEL_OUTPUT"
training_timestamp: "$TIMESTAMP"
EOF
    
    echo "💾 Training configuration saved to: $CONFIG_FILE"
    echo ""
    echo "🏃 Executing training command:"
    echo "$TRAIN_CMD"
    echo ""
    
    # Execute training with logging
    eval "$TRAIN_CMD" 2>&1 | tee "$LOG_FILE"
    
    if [[ $? -eq 0 ]]; then
        echo ""
        echo "🎉 Training completed successfully!"
        echo "📁 Model saved: $MODEL_OUTPUT"
        echo "📋 Training log: $LOG_FILE"
        echo "⚙️  Configuration: $CONFIG_FILE"
        
        # Show model info
        if [[ -f "$MODEL_OUTPUT" ]]; then
            MODEL_SIZE_KB=$(du -k "$MODEL_OUTPUT" | cut -f1)
            echo "📏 Model size: ${MODEL_SIZE_KB} KB"
            
            if [[ $MODEL_SIZE_KB -gt 150 ]]; then
                echo "⚠️  Warning: Model size exceeds 140KB target for ESP32 firmware"
            else
                echo "✅ Model size fits ESP32 flash budget"
            fi
        fi
        
        echo ""
        echo "🔄 Next steps:"
        echo "1. Run validation: python scripts/validate_model.py \"$MODEL_OUTPUT\""
        echo "2. Convert for firmware: python scripts/convert_for_firmware.py \"$MODEL_OUTPUT\""
    else
        echo ""
        echo "❌ Training failed! Check the log file for details: $LOG_FILE"
        exit 1
    fi
}

# Parse command line arguments
if [[ $# -eq 0 ]]; then
    usage
fi

WAKE_WORD="$1"
shift

while [[ $# -gt 0 ]]; do
    case $1 in
        --epochs)
            EPOCHS="$2"
            shift 2
            ;;
        --batch_size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --learning_rate)
            LEARNING_RATE="$2"
            shift 2
            ;;
        --no_batch_norm)
            USE_BATCH_NORM=false
            shift
            ;;
        --help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if [[ -z "$WAKE_WORD" ]]; then
    echo "❌ Error: Wake word is required"
    usage
fi

echo "🎯 Wake Word Training - microWakeWord medium-12-bn"
echo "=================================================="
echo ""

# Validate inputs
if ! [[ "$EPOCHS" =~ ^[0-9]+$ ]] || [[ $EPOCHS -lt 1 ]]; then
    echo "❌ Error: Invalid epochs value: $EPOCHS"
    exit 1
fi

if ! [[ "$BATCH_SIZE" =~ ^[0-9]+$ ]] || [[ $BATCH_SIZE -lt 1 ]]; then
    echo "❌ Error: Invalid batch size value: $BATCH_SIZE"
    exit 1
fi

# Check if microwakeword-train is available
if ! command -v microwakeword-train &> /dev/null; then
    echo "❌ Error: microwakeword-train command not found"
    echo "Please install microWakeWord training tools:"
    echo "  pip install microwakeword"
    exit 1
fi

# Run training pipeline
check_data
prepare_training
train_model

echo ""
echo "🏁 Training pipeline completed!" 