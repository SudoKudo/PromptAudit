<?php
session_start();
require './../includes/dbconfig.php';

$user = mysql_real_escape_string($_SESSION['user']);


if(!isset($user))
{
    header('Location: ./../login.php');
}

// Getting User Balance and data.

$userQuery = "SELECT * FROM userData WHERE userId1='$user' or userId2='$user' ; ";
$userResult = mysql_query($userQuery);

if(isset($userResult))
{
    $userBalance = mysql_result($userResult,0,"actualBalance");
    $userTeamId  = mysql_result($userResult,0,"teamId");
}

$squadQuery = "SELECT * FROM confirmedSquad WHERE teamId=$userTeamId";
$squadResult = mysql_query($squadQuery);

$jsonarray = [];

for($i=0;$i<mysql_num_rows($squadResult);$i++)
{
    $playerId    = mysql_result($squadResult,$i,"playerId");

    $playerQuery = "SELECT * FROM players WHERE playerId=$playerId";
    $playerResult = mysql_query($playerQuery);


    $playerName    = mysql_result($playerResult,0,"name");
    $playerCountry = mysql_result($playerResult,0,"country");
    $playerType    = mysql_result($playerResult,0,"type");
    $playerCaptain = mysql_result($playerResult,0,"captain");

    $pcostquery = "SELECT * FROM playerData where playerId=$playerId";
    $pcostresult = mysql_query($pcostquery);
    $pcost = mysql_result($pcostresult,0,"cost");

        if(strpos($playerType,'tsman')) $pclass = 'batsman';
        else if(strpos($playerType,'keeper')) $pclass = 'wkeeper';
        else if(strpos($playerType,'Rounder')) $pclass = 'rounder';
        else if(strpos($playerType,'Bowler')) $pclass = 'bowler';

        if($playerCaptain!="") $pclass = $pclass." captain";


    $obj['playerId'] = $playerId;
    $obj['playerName'] = $playerName;
    $obj['playerCountry'] = $playerCountry;
    $obj['playerType'] = $playerType;
    $obj['playerCaptain'] = $playerCaptain;
    $obj['playerClass'] = $pclass;
    $obj['playerCost'] = $pcost;
    $jsonarray[] = $obj;
}

$jsonString = json_encode($jsonarray,JSON_PRETTY_PRINT);
//echo("Number of results ".mysql_num_rows($playerResult)." <br>");
echo($jsonString);

?>
