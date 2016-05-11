#Game-API-Design:

## Set-Up Instructions:
1.  Update the value of application in app.yaml to the app ID you have registered
 in the App Engine admin console and would like to use to host your instance of this sample.
2.  Run the app with the devserver using dev_appserver.py DIR, and ensure it's
 running by visiting the API Explorer - by default localhost:8080/_ah/api/explorer.
3.  (Optional) Generate your client library(ies) with the endpoints tool.
 Deploy your application. 
 
##Game Description:
This is a two-player number guessing game. Player picks a date, ranging from 1st to 31st.
(Assume 31 days in a month).  'pick_a_dates' are sent to the `make_move` endpoint which will reply
with either: 'too early', 'too late', 'you win', or 'game over' (if the maximum
number of attempts is reached).
Different games can be played by many different users at any given time.  A user can create & play different games 
at the same time.  However when replaying an existing game, the previous session of that game with all its records 
might be overwritten by the new game's record if their keys are happened to be exactly the same.  Each game can be 
retrieved or played by using the path parameter `urlsafe_game_key`.

## Game Rules and Score-keeping:
A dealer can choose how many attempts are allowed for each game. The two players can not be the same user in a game.
If a gambler picked the right date within the number of allowed attempts, the gambler wins.  Otherwise, the dealer wins.
The winner of the game will get 1 point added to his/her total points, the loser will have 1 point deducted from his/her
total points. But if a gambler won and his/her remaining guesses are greater than the half of allowed attempts, the 
gambler gets double points (which are 2 points) added to his/her total points and the dealer loses 2 points.  Also, if 
gambler won and the allowed attempts are less than 3, then gambler gets a Jackpot of 10 points added, dealer loses 10 
points.

##Files Included:
 - api.py: Contains endpoints and game playing logic.
 - app.yaml: App configuration.
 - cron.yaml: Cronjob configuration.
 - main.py: Handler for taskqueue handler.
 - models.py: Entity and message definitions including helper methods.
 - utils.py: Helper function for retrieving ndb.Models by urlsafe Key string.

##Endpoints Included:
 - **create_user**
    - Path: 'user'
    - Method: POST
    - Parameters: `user_name`, `email` (optional)
    - Returns: Message confirming creation of the User.
    - Description: Creates a new User. `user_name` provided must be unique. Will 
    raise a ConflictException if a User with this `user_name` already exists.
    
 - **new_game**
    - Path: 'game'
    - Method: POST
    - Parameters: `dealer_name`, `gambler_name`, `attempts`
    - Returns: GameForm with initial game state.
    - Description: Creates a new Game. `dealer_name` and `gambler_name`provided must correspond to an existing 
    user - will raise a NotFoundException if not. To increase game's difficulty level, Number of `attempts` must be less 
    than 30 and greater than 1.  Otherwise, a form with a warning message will be returned.  If game is already exist 
    and not completed, the existing game form will be returned.  But if the existing game is completed, a new game form
    will be returned and the existing game's record will be overwritten by the new game's record.  Also adds a task to 
    a task queue to update the average moves remaining for active games.
     
 - **get_game**
    - Path: 'game/{urlsafe_game_key}'
    - Method: GET
    - Parameters: `urlsafe_game_key`
    - Returns: GameForm with current game state.
    - Description: Returns the current state of a game.
    
 - **get_user_games**
    - Path: 'games/user/{user_name}'
    - Method: GET
    - Parameters: `user_name`
    - Returns: GameForms 
    - Description: Returns all the active games played by the user with this `user_name`
        
 - **make_move**
    - Path: 'game/{urlsafe_game_key}'
    - Method: PUT
    - Parameters: `urlsafe_game_key`, `pick_a_date`
    - Returns: GameForm with new game state.
    - Description: Accepts a `pick_a_date` and returns the updated state of the game.
    If this causes a game to end, a corresponding Score entity will be created.
    
 - **cancel_game**
    - Path: 'game/{urlsafe_game_key}/cancel'
    - Method: DELETE
    - Parameters: `urlsafe_game_key`
    - Returns: StringMessage with canceled `urlsafe_game_key`.
    - Description: Returns a message confirming the cancellation of the game. 
    Canceling an non-existent or completed game will raise a BadRequestException or NotFoundException
 
 - **get_scores**
    - Path: 'scores'
    - Method: GET
    - Parameters: None
    - Returns: ScoreForms.
    - Description: Returns all Scores in the database (unordered).
    
 - **get_user_scores**
    - Path: 'scores/user/{user_name}'
    - Method: GET
    - Parameters: `user_name`
    - Returns: ScoreForms
    - Description: Returns all Scores recorded by the provided player (unordered).
    Will raise a NotFoundException if the User does not exist.
    
 - **get_high_scores**
    - Path: 'user/high_scores'
    - Method: GET
    - Parameters: `LimitResults`
    - Returns: UserForms
    - Description: Returns number of Scores in the database limited by `LimitResults` and ordered by `num_of_wons` in 
     descending order.
    Will returns all Scores in the database if there's no value from `LimitResults` and ordered by `User.name` in 
    Alphabetical order
 
 - **get_rankings**
    - Path: 'user/rankings'
    - Method: GET
    - Parameters: None
    - Returns: UserForms
    - Description: Returns all Scores in the database ordered by users' `total_points` records in descending order.
    
 - **get_game_history**
    - Path: 'game/{urlsafe_game_key}/history'
    - Method: GET
    - Parameters: `urlsafe_game_key`
    - Returns: StringMessage
    - Description: Returns a list of dictionary-pairs of messages and guesses recorded in `make_move`.
    
 - **get_active_game_count**
    - Path: 'games/active'
    - Method: GET
    - Parameters: None
    - Returns: StringMessage
    - Description: Gets the average number of attempts remaining for all games
    from a previously cached memcache key.

##Models Included:
 - **User**
    - Stores unique user_name and (optional) email address.
    
 - **Game**
    - Stores unique game states. Associated with User model via KeyProperty.
    
 - **Score**
    - Records completed games. Associated with Users model via KeyProperty.
    
##Forms Included:
 - **GameForm**
    - Representation of a Game's state (urlsafe_key, attempts_remaining,
    game_over flag, message, user_name).
 - **GameForms**
    - Representation of a Game's state (urlsafe_key, attempts_remaining,
    game_over flag, message, user_name).
 - **NewGameForm**
    - Used to create a new game (user_name, min, max, attempts)
 - **MakeMoveForm**
    - Inbound make move form (guess).
 - **ScoreForm**
    - Representation of a completed game's Score (user_name, date, won flag,
    guesses).
 - **ScoreForms**
    - Multiple ScoreForm container.
 - **UserForm**
    - Representation of a user profile.
 - **UserForms**
    - Multiple UserForm container. 
 - **StringMessage**
    - General purpose String container.
 - **LimitResults**
    - General purpose String container.
    