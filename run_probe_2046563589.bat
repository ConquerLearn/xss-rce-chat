@echo off
REM run_probe_2046563589.bat —— 定向到账号 2046563589 的连通性探针（先发 1 条无害消息验证管道）
REM 用法： run_probe_2046563589.bat <TzdInjectorNTQQ根目录>
REM   前置：本机已启动并登录 QQ，且【手动打开与 2046563589 的聊天窗口】
REM   例： run_probe_2046563589.bat D:\tools\TzdInjectorNTQQ
setlocal
set PROJECT_ROOT=%~1
if "%PROJECT_ROOT%"=="" (
  echo 用法: run_probe_2046563589.bat ^<TzdInjectorNTQQ根目录^>
  echo   前置: 本机已登录 QQ，且已打开与 2046563589 的聊天窗口
  exit /b 1
)
set PAYLOAD=%~dp0probe_2046563589.txt
set LIMIT=1
set DELAY=1500
set TARGET=2046563589

REM 1) 把驱动壳拷进项目源码树（com.electron 包）
copy /Y "%~dp0QQXssDriver.java" "%PROJECT_ROOT%\src\main\java\com\electron\QQXssDriver.java" >nul
if errorlevel 1 (
  echo [!] 无法写入 %PROJECT_ROOT%\src\main\java\com\electron\ ，请确认项目结构
  exit /b 1
)

REM 2) 构建（需要 Java 11+ 与联网拉 Gradle 依赖）
cd /d "%PROJECT_ROOT%"
call gradlew.bat build
if errorlevel 1 (
  echo [!] gradlew build 失败，请检查 Java/Gradle 环境
  exit /b 1
)

REM 3) 运行（cwd 必须在项目根，ElectronInjector.dll 在此处被 System.load 加载）
for %%j in (build\libs\*.jar) do set JAR=%%j
echo [*] 运行: java -cp %JAR% com.electron.QQXssDriver "%PAYLOAD%" %LIMIT% %DELAY% "" %TARGET%
echo [*] 守卫: 发送前会扫描页面文本确认当前聊天对象含 2046563589，发错窗口会被跳过
java -cp "%JAR%" com.electron.QQXssDriver "%PAYLOAD%" %LIMIT% %DELAY% "" %TARGET%
endlocal
