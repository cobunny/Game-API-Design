# -*- coding: utf-8 -*-`
"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""

import logging
import endpoints
import re
from protorpc import remote, messages
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import User, Game, Score
from models import StringMessage, NewGameForm, GameForm, GameForms, MakeMoveForm, \
    ScoreForms, LimitResults, UserForm, UserForms
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


# - - - - GameAPIDesign Endpoints - - - - - - - - - - - - - - - - - - - - - - - - -

@endpoints.api(name='gameapidesign', version='v1')
class GameAPIDesign(remote.Service):
    """Game API"""

    # - - - - Create user endpoint - - - - - - - - - - - - - - - 
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

    # - - - - New game endpoint - - - - - - - - - - - - - - -
    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates new game"""
        dealer = User.query(User.name == request.dealer_name).get()
        gambler = User.query(User.name == request.gambler_name).get()
        # Validate user
        if not dealer or not gambler or not dealer and gambler:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')

        if request.attempts < 1 or request.attempts > 30:
            raise endpoints.BadRequestException('Number of attempts must be less than 30 and greater than 1')

        # Check to see if game already exist.
        games = Game.query(ndb.AND(Game.gambler == gambler.key, Game.dealer == dealer.key)).fetch()

        if games:
            for game in games:
                if game.attempts_allowed == request.attempts and game.game_over == False:
                    return game.to_form('Game already exist. Continue to play!')

        game = Game.new_game(dealer.key, gambler.key, request.attempts)

        # Use a task queue to update the average attempts remaining.
        # This operation is not needed to complete the creation of a new game
        # so it is performed out of sequence.
        taskqueue.add(url='/tasks/cache_average_attempts')
        return game.to_form('Good luck playing games!')

    # - - - - Get game endpoint - - - - - - - - - - - - - - -
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

    # - - - - Get user game endpoint - - - - - - - - - - - - - - -
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

        games = Game.query(ndb.OR(Game.dealer == user.key, Game.gambler == user.key)). \
            filter(Game.game_over == False)
        return GameForms(items=[game.to_form('Time to make a move!') for game in games])

    # - - - - Make move endpoint - - - - - - - - - - - - - - -
    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move. Returns a game state with message"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            dealer = game.dealer.get()
            gambler = game.gambler.get()

            # Check to see if game is already finished
            if game.game_over:
                game.add_game_history('Game already over!', None, None)
                return game.to_form('Game already over!')

            # Check to see if valid guess
            if request.pick_a_date > 31 or request.pick_a_date < 1:
                game.add_game_history('Invalid guess! No such date!', game.attempts_allowed - game.attempts_remaining,
                                      request.pick_a_date)
                return game.to_form('Invalid guess! No such date!')


            else:
                game.attempts_remaining -= 1
                # If the dates match, gambler win.
                if request.pick_a_date == game.target:
                    if game.attempts_remaining > int(game.attempts_allowed / 2):
                        gambler.total_points += 2
                        dealer.total_points -= 2
                    # Hit the jackpot
                    if game.attempts_allowed < 3:
                        gambler.total_points += 10
                        dealer.total_points -= 10
                    gambler.total_points += 1
                    dealer.total_points -= 1
                    dealer.put()
                    gambler.put()
                    game.won = True
                    game.add_game_history('Congratulations! You picked the correct date.',
                                          game.attempts_allowed - game.attempts_remaining, request.pick_a_date)
                    game.end_game(game.won, dealer.key, gambler.key)
                    game.put()
                    return game.to_form('You win!')

                # If guess is incorrect, warn gambler and try again
                if request.pick_a_date < game.target:
                    msg = 'Maybe too early for a bonus!'
                    game.add_game_history('You guessed higher.', game.attempts_allowed - game.attempts_remaining,
                                          request.pick_a_date)
                else:
                    msg = 'A little too late, a bonus comes sooner than that!'
                    game.add_game_history('You guessed lower.', game.attempts_allowed - game.attempts_remaining,
                                          request.pick_a_date)

                # Gambler guesses incorrectly and exceeded limited attempts, so game over.
                if game.attempts_remaining < 1:
                    gambler.total_points -= 1
                    dealer.total_points += 1
                    dealer.put()
                    gambler.put()
                    game.won = False
                    game.add_game_history('Incorrect. Game over!', game.attempts_allowed - game.attempts_remaining,
                                          request.pick_a_date)
                    game.end_game(game.won, dealer.key, gambler.key)
                    game.put()
                    return game.to_form(msg + ' Game over!')
                else:
                    game.put()
                    return game.to_form(msg)

        raise endpoints.BadRequestException('User_name not found! Or game already over! Or something else...')

    # - - - - Cancel game endpoint - - - - - - - - - - - - - - -
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

    # - - - - Get scores endpoint - - - - - - - - - - - - - - -
    @endpoints.method(response_message=ScoreForms,
                      path='scores',
                      name='get_scores',
                      http_method='GET')
    def get_scores(self, request):
        """Return all scores"""
        scores = Score.query().order(-Score.date)

        return ScoreForms(items=[score.to_form() for score in scores])

    # - - - - Get user scores endpoint - - - - - - - - - - - - - - -
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
        scores = Score.query(ndb.OR(Score.dealer == user.key, Score.gambler == user.key))
        return ScoreForms(items=[score.to_form() for score in scores])

    # - - - - Get high scores endpoint - - - - - - - - - - - - - - -
    @endpoints.method(request_message=LimitResults,
                      response_message=UserForms,
                      path='user/high_scores',
                      name='get_high_scores',
                      http_method='GET')
    def get_high_scores(self, request):
        """Return all scores ordered by total points"""
        if request.limit:
            users = User.query().order(-User.total_points).fetch(request.limit)
        else:
            users = User.query().order(User.name).fetch()

        return UserForms(items=[user.to_form() for user in users])

    # - - - - Get user rankings endpoint - - - - - - - - - - - - - - -
    @endpoints.method(response_message=UserForms,
                      path='user/rankings',
                      name='get_rankings',
                      http_method='GET')
    def get_rankings(self, request):
        """Returns all players ranked by their total points."""
        users = User.query().order(-User.total_points).fetch()

        return UserForms(items=[user.to_form() for user in users])

    # - - - - Get game history endpoint - - - - - - - - - - - - - - -
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

    # - - - - Get average attempts remaining endpoint - - - - - - - - - - - - - - -
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


api = endpoints.api_server([GameAPIDesign])
