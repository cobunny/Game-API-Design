"""models.py - This file contains the class definitions for the Datastore
entities used by the Game. Because these classes are also regular Python
classes they can include methods (such as 'to_form' and 'new_game')."""

import random
from datetime import date
from protorpc import messages
from google.appengine.ext import ndb


class User(ndb.Model):
    """User profile"""
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()
    total_points = ndb.IntegerProperty(required=True, default=0)

    def to_form(self):
        """Returns UserForm"""
        form = UserForm()
        form.name = self.name
        form.email = self.email
        form.total_points = self.total_points
        return form


class Game(ndb.Model):
    """Game object"""
    target = ndb.IntegerProperty(required=True)
    attempts_allowed = ndb.IntegerProperty(required=True)
    attempts_remaining = ndb.IntegerProperty(required=True)
    game_canceled = ndb.BooleanProperty(required=True, default=False)
    game_over = ndb.BooleanProperty(required=True, default=False)
    won = ndb.BooleanProperty(required=True, default=False)
    dealer = ndb.KeyProperty(required=True, kind='User')
    gambler = ndb.KeyProperty(required=True, kind='User')
    history = ndb.PickleProperty(required=True, default=[])

    @classmethod
    def new_game(cls, dealer, gambler, attempts):
        """Creates and returns a new game"""
        game = Game(dealer=dealer,
                    gambler=gambler,
                    target=random.choice(range(1, 32)),
                    attempts_allowed=attempts,
                    attempts_remaining=attempts,
                    game_over=False,
                    won=False)
        game.history = []
        game.put()
        return game

    def to_form(self, message):
        """Returns a GameForm representation of the Game"""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.dealer_name = self.dealer.get().name
        form.gambler_name = self.gambler.get().name
        form.attempts_remaining = self.attempts_remaining
        form.dealer_total_points = self.dealer.get().total_points
        form.gambler_total_points = self.gambler.get().total_points
        form.game_over = self.game_over
        form.won = self.won
        form.message = message
        return form

    def end_game(self, won, dealer, gambler):
        """Ends the game - if won is True, the player won. - if won is False,
        the player lost."""
        self.game_over = True
        self.dealer = dealer
        self.gambler = gambler
        self.put()
        # Add the game to the score 'board'
        score = Score(dealer=self.dealer, gambler=self.gambler, date=date.today(), won=won,
                      guesses=self.attempts_allowed - self.attempts_remaining)
        score.put()

    def canceled_game(self):
        self.game_canceled = True
        self.put()

    def add_game_history(self, result, guesses, pick_a_date):
        if isinstance(result, str):
            self.history.append({'message': result, 'nth_guess': guesses, 'your guess': pick_a_date})
            self.history = self.history
            self.put()
        else:
            raise


class Score(ndb.Model):
    """Score object"""
    dealer = ndb.KeyProperty(required=True, kind='User')
    gambler = ndb.KeyProperty(required=True, kind='User')
    date = ndb.DateProperty(required=True)
    won = ndb.BooleanProperty(required=True, default=False)
    guesses = ndb.IntegerProperty(required=True)

    def to_form(self):
        return ScoreForm(dealer_name=self.dealer.get().name, gambler_name=self.gambler.get().name, won=self.won,
                         date=str(self.date), guesses=self.guesses, dealer_total_points=self.dealer.get().total_points,
                         gambler_total_points=self.gambler.get().total_points)


class GameForm(messages.Message):
    """GameForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    attempts_remaining = messages.IntegerField(2, required=True)
    game_over = messages.BooleanField(3, required=True)
    message = messages.StringField(4, required=True)
    dealer_name = messages.StringField(5, required=True)
    gambler_name = messages.StringField(6, required=True)
    dealer_total_points = messages.IntegerField(7, required=True)
    gambler_total_points = messages.IntegerField(8, required=True)
    won = messages.BooleanField(9, required=True)


class GameForms(messages.Message):
    """Return multiple ScoreForms"""
    items = messages.MessageField(GameForm, 1, repeated=True)


class NewGameForm(messages.Message):
    """Used to create a new game"""
    gambler_name = messages.StringField(1, required=True)
    dealer_name = messages.StringField(2, required=True)
    attempts = messages.IntegerField(3, required=True)


class MakeMoveForm(messages.Message):
    """Used to make a move in an existing game"""
    pick_a_date = messages.IntegerField(1, required=True)


class ScoreForm(messages.Message):
    """ScoreForm for outbound Score information"""
    gambler_name = messages.StringField(1, required=True)
    dealer_name = messages.StringField(2, required=True)
    date = messages.StringField(3, required=True)
    won = messages.BooleanField(4, required=True)
    guesses = messages.IntegerField(5, required=True)
    dealer_total_points = messages.IntegerField(6, required=True)
    gambler_total_points = messages.IntegerField(7, required=True)


class ScoreForms(messages.Message):
    """Return multiple ScoreForms"""
    items = messages.MessageField(ScoreForm, 1, repeated=True)


class UserForm(messages.Message):
    """ScoreForm for outbound Score information"""
    name = messages.StringField(1, required=True)
    email = messages.StringField(2)
    total_points = messages.IntegerField(3, required=True)


class UserForms(messages.Message):
    """Return multiple UserForms"""
    items = messages.MessageField(UserForm, 1, repeated=True)


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)


class LimitResults(messages.Message):
    """StringMessage-- outbound (single) string message"""
    limit = messages.IntegerField(1)
