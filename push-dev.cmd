@echo off
echo Iniciando proceso


%@Try%
    cf login -a  https://api.cf.br10.hana.ondemand.com -u "%cf_u_tesista%" -p "%cf_p_tesista%" -o SCP_CyT_app-devqa-cii-cf-sp  -s tesistas
    cf push capstonebackend --docker-image lucianoatm/capstonebackend
    
%@EndTry%
:@Catch
    echo ""
:@EndCatch
 
echo Fin del proceso