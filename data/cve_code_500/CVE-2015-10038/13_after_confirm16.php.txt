<?php
session_start();
require './../includes/dbconfig.php';
$user = mysql_real_escape_string($_SESSION['user']);
if(!isset($user))
{
    header('Location: ./../login.php');
}

$idString = mysql_real_escape_string($_POST['c16']);
$ids = explode(',',$idString);
sort($ids);

//// For Debugging
//for($i=0;$i<16;$i++)
//    echo($ids[$i]."\n");

// Getting User Balance and data.

$userQuery = "SELECT * FROM userData WHERE userId1='$user' or userId2='$user' ; ";
$userResult = mysql_query($userQuery);

if(isset($userResult))
{
    $userBalance = mysql_result($userResult,0,"actualBalance");
    $userTeamId  = mysql_result($userResult,0,"teamId");
    $transferNum = mysql_result($userResult,0,"transferNum");

}

$oldSquadQuery = "SELECT * FROM confirmedSquad where teamId='".$userTeamId."';";
$oldSquadResult = mysql_query($oldSquadQuery);
$oldids = [];

for($i=0;$i<mysql_num_rows($oldSquadResult);$i++)
{
    $oldids[] = mysql_result($oldSquadResult,$i,"playerId");
}

sort($oldids);
$numchanges = 0;
for($i=0;$i<16;$i++)
{
    if(!in_array($ids[$i],$oldids))
    {
        $numchanges++;
    }
}

//Exiting if user does not have sufficient transfers
if($numchanges > $transferNum)
{
    echo("Insufficient Number of transfers!! \nCannot Confirm Squad");
    exit();
}

//Deleting existing confirmedSquad before Copying And clearing the show P11

$deleteQuery    = "DELETE FROM confirmedSquad where teamId=".$userTeamId.";";
$deleteResult   = mysql_query($deleteQuery);

$clearP11Query  = "DELETE FROM userP11 where teamId=".$userTeamId.";";
$clearP11Result = mysql_query($clearP11Query);

// Code for getting new balance

$spent = 0;

for($i=0;$i<count($ids);$i++)
{
    $balplayerId = $ids[$i];

    $balplayerQuery = "SELECT * FROM playerData WHERE playerId='$balplayerId' ;";
    $balplayerResult = mysql_query($balplayerQuery);

    $pcost = intval(mysql_result($balplayerResult,0,"cost"));
    $spent = $spent + $pcost;
}
for($i=0;$i<count($oldids);$i++)
{
    $balplayerId = $oldids[$i];

    $balplayerQuery = "SELECT * FROM playerData WHERE playerId='$balplayerId' ;";
    $balplayerResult = mysql_query($balplayerQuery);

    $pcost = (mysql_result($balplayerResult,0,"cost"));
    $spent = $spent - $pcost;
}

$newBalance = $userBalance - $spent;

//echo($spent."spent");

// Adding the new players into the confirmed squad table.

for($i=0;$i<count($ids);$i++)
{

    $playerId = $ids[$i];

    $playerQuery = "SELECT * FROM playerData WHERE playerId='$playerId' ;";
    $playerResult = mysql_query($playerQuery);


    if(isset($playerResult))
    {
        $playerCost       = mysql_result($playerResult,0,"cost");
        $playerForm       = mysql_result($playerResult,0,"form");
        $playerConfidence = mysql_result($playerResult,0,"confidence");
    }

    $transferQuery = "INSERT INTO confirmedSquad VALUES ('$userTeamId','$playerId','$playerForm','$playerConfidence'); ";
    $transferresult = mysql_query($transferQuery);
}

//Update the balance and number of transfers

$balanceUpdateQuery = "UPDATE userData SET actualBalance=$newBalance WHERE teamId=$userTeamId";
$balanceUpdateResult = mysql_query($balanceUpdateQuery);

$transferUpdateQuery = "UPDATE userData SET transferNum = transferNum - $numchanges WHERE teamId = $userTeamId";
$transferUpdateResult = mysql_query($transferUpdateQuery);
echo("Your Squad has been confirmed\n");
echo("You may now choose your playing 11");
//echo($newBalance);
//echo($clearP11Query);
//echo($deleteQuery);
