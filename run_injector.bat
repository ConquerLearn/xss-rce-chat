@echo off
REM run_injector.bat —— 构建并运行 TzdInjectorNTQQ 驱动壳
REM 用法： run_injector.bat <TzdInjectorNTQQ根目录> [payload文件] [limit] [delayMs]
REM   例： run_injector.bat D:\tools\TzdInjectorNTQQ  "C:\Users\Administrator\WorkBuddy\2026-09-11-17-41-47\qq_xss_test\payload_sample_30.txt" 30 800
setlocal
set PROJECT_ROOT=%~1
if "%PROJECT_ROOT%"=="" (
  echo 用法: run_injector.bat ^<TzdInjectorNTQQ根目录^> [payload] [limit] [delayMs]
  exit /b 1
)
set PAYLOAD=%~2
if "%PAYLOAD%"=="" set PAYLOAD=%~dp0payload_sample_30.txt
set LIMIT=%~3
if "%LIMIT%"=="" set LIMIT=30
set DELAY=%~4
if "%DELAY%"=="" set DELAY=800

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
echo [*] 运行: java -cp %JAR% com.electron.QQXssDriver "%PAYLOAD%" %LIMIT% %DELAY%
java -cp "%JAR%" com.electron.QQXssDriver "%PAYLOAD%" %LIMIT% %DELAY%
endlocal
