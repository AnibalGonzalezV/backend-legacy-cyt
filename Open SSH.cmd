@echo off

@ECHO. 
@ECHO.
echo 	**********************
echo   	     OPEN SSH APP: ucnback
echo 	**********************
@ECHO. 
@ECHO.

%@Try%

	:: Login
	cf login -a  https://api.cf.br10.hana.ondemand.com -u "%cf_u_tesista%" -p "%cf_p_tesista%" -o SCP_CyT_app-devqa-cii-cf-sp  -s tesistas

	:: 2) HABILITACIONDE PERMISOS [Solo una vez]
	::cf allow-space-ssh tesistas
	::cf enable-ssh ucnback
	::cf restart ucnback

	
	:: 3) Conexion SSH
	cf ssh-code		
	cf ssh ucnback
	
	
%@EndTry%
:@Catch
    echo ""
:@EndCatch




cmd /k