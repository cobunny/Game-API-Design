# -*- coding: utf-8 -*-`
"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""

import logging
import endpoints
from protorpc import remote, messages
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import User, Game, Score
from models import StringMessage, NewGameForm, GameForm, GameForms, MakeMoveForm, \
    ScoreForms, LimitResults
from utils import get_by_urlsafe

NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
GET_GAME_REQUEST = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1), )
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1), )

USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1, required=True),
                                           email=messages.StringField(2))

MEMCACHE_MOVES_REMAINING = 'MOVES_REMAINING'


@endpoints.api(name='get_your_bonus_day', version='v1')
class GetYourBonusDayApi(remote.Service):
    """Game API"""

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=StringMessage,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create a User. Requires a unique username"""
        if User.query(User.name == request.user_name).get():
            raise endpoints.ConflictException(
                'A User with that name already exists!')
        user = User(name=request.user_name, email=request.email)
        user.put()
        return StringMessage(message='User {} created!'.format(
            request.user_name))

    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates new game"""
        user = User.query(User.name == request.user_name).get()
        # Validate user
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')

        game = Game.new_game(user.key, request.attempts)

        # Use a task queue to update the average attempts remaining.
        # This operation is not needed to complete the creation of a new game
        # so it is performed out of sequence.
        taskqueue.add(url='/tasks/cache_average_attempts')
        return game.to_form('Good luck playing Get Your Bonus Day!')

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Return the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            return game.to_form('Time to make a move!')
        else:
            raise endpoints.NotFoundException('Game not found!')

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=GameForms,
                      path='games/user/{user_name}',
                      name='get_user_games',
                      http_method='GET')
    def get_user_games(self, request):
        """Returns all of an individual User's games"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')
        games = Game.query(Game.user == user.key). \
            filter(Game.game_over == False)
        return GameForms(items=[game.to_form('Time to make a move!') for game in games])

    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move. Returns a game state with message"""

        game = get_by_urlsafe(request.urlsafe_game_key, Game)

        user = User.query(User.name == request.user_name).get()

        # Validate user
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')

        # Validate game and player
        if game and user.key == game.user:

            # Check to see if game is already finished
            if game.game_over:
                game.add_game_history('Game already over!', game.attempts_allowed - game.attempts_remaining)
                user.game_over = True
                user.put()
                return game.to_form('Game already over!')

            # Check to see if valid guess
            if request.pick_a_date > 31 or request.pick_a_date < 1:
                game.add_game_history('Invalid guess! No such date!', game.attempts_allowed - game.attempts_remaining)
                return game.to_form('Invalid guess! No such date!')


            else:
                game.attempts_remaining -= 1
                 # If the dates match, user win.
                if request.pick_a_date == game.target:
                    user.num_of_wons +=1
                    user.game_over= True
                    user.put()
                    game.num_of_wons = user.num_of_wons
                    game.won = True
                    game.add_game_history('Congratulations! You picked the correct date.', game.attempts_allowed - game.attempts_remaining)
                    game.end_game(game.won, game.num_of_wons)
                    game.put()
                    return game.to_form('You win!')

                # If guess is incorrect, warn user and try again
                if request.pick_a_date < game.target:
                    msg = 'Maybe too early for a bonus!'
                    game.add_game_history('You guessed higher.', game.attempts_allowed - game.attempts_remaining)
                else:
                    msg = 'A little too late, a bonus comes sooner than that!'
                    game.add_game_history('You guessed lower.', game.attempts_allowed - game.attempts_remaining)

                # User guesses incorrectly and exceeded limited attempts, so game over  
                if game.attempts_remaining < 1:
                    user.num_of_wons ==user.num_of_wons
                    user.game_over = True
                    user.put()
                    game.won = False
                    game.num_of_wons = user.num_of_wons
                    game.add_game_history('Incorrect. Game over!', game.attempts_allowed - game.attempts_remaining)
                    game.end_game(game.won, game.num_of_wons)
                    
                game.put()
                return game.to_form(msg + ' Game over!')


        raise endpoints.BadRequestException('User_name not found! Or game already created! Or something else...')

    @endpoints.method(request_message=GET_GAME_REQUEST, response_message=StringMessage,
                      path='game/{urlsafe_game_key}/cancel',
                      http_method='DELETE', name='cancel_game')
    def cancel_game(self, request):
        """Cancel an active game."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)

        if game and not game.game_over:
            game.canceled_game()
            game.key.delete()
            return StringMessage(message='Game with key: {} deleted.'.
                                 format(request.urlsafe_game_key))

        elif game and game.game_over:
            raise endpoints.BadRequestException(
                'Cannot cancel a completed game!')
        else:
            raise endpoints.NotFoundException('That game does not exist!')

    @endpoints.method(response_message=ScoreForms,
                      path='scores',
                      name='get_scores',
                      http_method='GET')
    def get_scores(self, request):
        """Return all scores"""
        scores = Score.query().order(Score.user)

        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=ScoreForms,
                      path='scores/user/{user_name}',
                      name='get_user_scores',
                      http_method='GET')
    def get_user_scores(self, request):
        """Returns all of an individual User's scores"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')
        scores = Score.query(Score.user == user.key)
        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoints.method(request_message=LimitResults,
                      response_message=ScoreForms,
                      path='scores/high_scores',
                      name='get_high_scores',
                      http_method='GET')
    def get_high_scores(self, request):
        """Return all scores ordered by total points"""
        if request.limit:
            scores = Score.query().order(-Score.num_of_wons).fetch(request.limit)

        else:
            scores = Score.query().order(-Score.num_of_wons).get()

        return ScoreForms(items=[score.to_form() for score in scores])


    @endpoints.method(response_message=ScoreForms,
                      path='scores/user_rankings',
                      name='get_user_rankings',
                      http_method='GET')
    def get_user_rankings(self, request):
        """Return all scores ordered by numbers of won"""
        scores = Score.query().filter(Score.won == True).order(-Score.num_of_wons)
       
        return ScoreForms(items=[score.to_form() for score in scores])


    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=StringMessage,
                      path='game/{urlsafe_game_key}/history',
                      name='get_game_history',
                      http_method='GET')
    def get_game_history(self, request):
        """Returns a summary of a game's guesses."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if not game:
            raise endpoints.NotFoundException('Game not found')
       
        return StringMessage(message=str(game.history))



    @endpoints.method(response_message=StringMessage,
                      path='games/average_attempts',
                      name='get_average_attempts_remaining',
                      http_method='GET')

    def get_average_attempts(self, request):
        """Get the cached average moves remaining"""
        return StringMessage(message=memcache.get(MEMCACHE_MOVES_REMAINING) or '')

    @staticmethod
    def _cache_average_attempts():
        """Populates memcache with the average moves remaining of Games"""
        games = Game.query(Game.game_over == False).fetch()
        if games:
            count = len(games)
            total_attempts_remaining = sum([game.attempts_remaining
                                            for game in games])
            average = float(total_attempts_remaining) / count
            memcache.set(MEMCACHE_MOVES_REMAINING,
                         'The average moves remaining is {:.2f}'.format(average))


api = endpoints.api_server([GetYourBonusDayApi])
