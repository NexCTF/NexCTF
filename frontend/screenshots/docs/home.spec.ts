import {
  ADMIN,
  openChallenges,
  openDashboard,
  openScoreboard,
  openSqlInjection,
  shot,
  wholePage,
} from "../support";

shot("home/admin_dashboard", ADMIN, openDashboard);

shot("home/challenges", ADMIN, openChallenges, wholePage);

shot("home/challenge_details", ADMIN, openSqlInjection);

shot("home/scoreboard", ADMIN, openScoreboard);
