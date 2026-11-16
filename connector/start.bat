@echo off
chcp 65001 >nul
title 知识中台 · 连接层

rem ==== 填你新建的应用 Key（不要用已经泄露的那条）====
set FG_KEY=fastgpt-在这里粘贴你的新Key
set FG_BASE=https://cloud.fastgpt.cn/api

echo.
echo   连接层启动中...
echo   然后双击同目录下的「原型-已连接FastGPT.html」，进「检索调试」页提问
echo   关闭本窗口即停止服务
echo.

python "%~dp0proxy.py"
pause
