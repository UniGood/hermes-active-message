#!/usr/bin/env bash
set -euo pipefail

# hermes-active-message 安装脚本
# 用法: bash install.sh

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "📦 安装 hermes-active-message ..."
echo "   HERMES_HOME: $HERMES_HOME"

# 1. 安装 Python 依赖
echo "📥 安装 Python 依赖 (pyyaml) ..."
pip3 install --quiet pyyaml 2>/dev/null || pip install --quiet pyyaml 2>/dev/null || {
    echo "⚠️  pyyaml 安装失败，请手动安装: pip3 install pyyaml"
}

# 2. 复制核心库 + 配置
echo "📁 复制核心文件 ..."
mkdir -p "$HERMES_HOME/active-message"
cp "$SCRIPT_DIR/lib/active_message_lib.py" "$HERMES_HOME/active-message/"
cp "$SCRIPT_DIR/scripts/build_context.py" "$HERMES_HOME/active-message/"

# 复制配置 (不覆盖已有配置)
if [ ! -f "$HERMES_HOME/active-message/config.yaml" ]; then
    cp "$SCRIPT_DIR/config.example.yaml" "$HERMES_HOME/active-message/config.yaml"
    echo "   ✅ 已创建默认配置: $HERMES_HOME/active-message/config.yaml"
    echo "   ⚠️  请编辑配置文件，填入 target_chat_id 和 target_user_id"
else
    echo "   ⏭️  配置文件已存在，跳过"
fi

# 3. 复制 cron prompt
mkdir -p "$HERMES_HOME/active-message"
cp "$SCRIPT_DIR/prompts/cron_prompt.txt" "$HERMES_HOME/active-message/"

# 4. 复制 plugin hook
echo "🔌 安装 plugin hook ..."
mkdir -p "$HERMES_HOME/plugins/active-message"
cp "$SCRIPT_DIR/plugin/__init__.py" "$HERMES_HOME/plugins/active-message/"
cp "$SCRIPT_DIR/plugin/plugin.yaml" "$HERMES_HOME/plugins/active-message/"

# 5. 复制 cron 入口脚本
echo "⏰ 安装 cron 脚本 ..."
mkdir -p "$HERMES_HOME/scripts"
cp "$SCRIPT_DIR/scripts/cron_entry.py" "$HERMES_HOME/scripts/active-message-build-context.py"
chmod +x "$HERMES_HOME/scripts/active-message-build-context.py"

# 6. 创建 .gitignore
cat > "$HERMES_HOME/active-message/.gitignore" << 'EOF'
state.json
config.yaml
__pycache__/
*.pyc
EOF

echo ""
echo "✅ 安装完成！"
echo ""
echo "📋 后续步骤:"
echo "   1. 编辑配置: $HERMES_HOME/active-message/config.yaml"
echo "   2. 在 Hermes config.yaml 中启用插件:"
echo "      plugins:"
echo "        enabled:"
echo "          - active-message"
echo "   3. 测试脚本: python3 $HERMES_HOME/active-message/build_context.py"
echo "   4. 创建 cron job (在 Hermes 对话中):"
echo "      让 Hermes 执行: hermes cron create \"0,20,40 6-23 * * *\" \\"
echo "        \"\$(< $HERMES_HOME/active-message/cron_prompt.txt)\" \\"
echo "        --name active-message \\"
echo "        --script active-message-build-context.py \\"
echo "        --deliver <platform>:<chat_id>"
echo "   5. 重启 gateway 使 plugin hook 生效"
echo ""
