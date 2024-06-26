"""
Handles tasks that happen each game round
"""

import importlib
import multiprocessing
import random
import time
from time import perf_counter, sleep

import win32gui
from win32con import BM_CLICK

import arena_functions
import game_assets
import game_functions
import screen_coords
import settings
from arena import Arena
from comps import CompsManager
from vec2 import Vec2
from vec4 import Vec4


class Game:
    """Game class that handles game logic such as round tasks"""

    def __init__(
        self, message_queue: multiprocessing.Queue, comps: CompsManager
    ) -> None:
        """Initialize the Game instance.

        Args:
            message_queue (multiprocessing.Queue): The message queue.
            comps (CompsManager): The CompsManager instance.
        """
        importlib.reload(game_assets)
        self.message_queue = message_queue
        self.comps_manager = comps
        self.arena = Arena(self.message_queue, comps)
        self.round: list[str, int] = ["0-0", 0]
        self.time = None
        self.forfeit_time = settings.FORFEIT_TIME + random.randint(50, 150)
        self.found_window = False
        self.start_time_of_round = None
        self.fast8_leveling = False

        print("\n[!] Searching for game window")
        while not self.found_window:
            print("  Did not find window, trying again...")
            win32gui.EnumWindows(self.find_window_callback, None)
            sleep(1)

        self.loading_screen()

    def find_window_callback(
        self,
        hwnd,
        extra,  # pylint: disable=unused-argument
    ) -> None:
        """Callback function to find the game window and get its size.

        Args:
            hwnd: The window handle.
            extra: Extra argument (unused in this case).
        """
        if "League of Legends (TM) Client" not in win32gui.GetWindowText(hwnd):
            return

        rect = win32gui.GetWindowRect(hwnd)

        x_pos = rect[0]
        y_pos = rect[1]
        width = rect[2] - x_pos
        height = rect[3] - y_pos

        if width < 200 or height < 200:
            return

        print(f"  Window {win32gui.GetWindowText(hwnd)} found")
        print(f"    Location: ({x_pos}, {y_pos})")
        print(f"    Size:     ({width}, {height})")
        Vec4.setup_screen(x_pos, y_pos, width, height)
        Vec2.setup_screen(x_pos, y_pos, width, height)
        self.found_window = True

    def loading_screen(self) -> None:
        """Loop that runs while the game is in the loading screen."""
        game_functions.default_pos()
        if self.comps_manager.current_comp()[0] == "High Value":
            self.fast8_leveling = True
        while game_functions.get_round()[0] != "1-1":
            if self.check_failed_to_connect_window():
                return
            sleep(1)
        self.start_time: float = perf_counter()
        self.game_loop()

    def check_failed_to_connect_window(self) -> bool:
        """Check "Failed to Connect" windows and try to reconnect"""
        hwnd = win32gui.FindWindow(None, "Failed to Connect")
        if hwnd:
            print('  Found "Failed to Connect" window, trying to exit and reconnect')
            if reconnect_button := win32gui.FindWindowEx(hwnd, 0, "Button", None):
                if cancel_button := win32gui.FindWindowEx(
                    hwnd, reconnect_button, "Button", None
                ):
                    print("  Exiting the game.")
                    win32gui.SendMessage(cancel_button, BM_CLICK, 0, 0)
                    return True
                print("  Cancel button not found.")
            else:
                print("  Reconnect button not found.")
        return False

    def game_loop(self) -> None:
        """Loop that runs while the game is active, handles calling the correct tasks for round and exiting game."""
        self.start_time_of_round = time.time()
        labels = [
            (
                f"{arena_functions.get_seconds_remaining()}",
                screen_coords.SECONDS_REMAINING_LOC.get_coords(),
                -40,
                -10,
            )
        ]
        self.message_queue.put(("LABEL", labels))

        ran_round: str = None
        last_game_health: int = 100

        while True:
            game_health: int = arena_functions.get_health()
            if game_health == 0 and last_game_health > 0:
                count: int = 15
                while count > 0:
                    if not game_functions.check_alive():
                        self.message_queue.put("CLEAR")
                        game_functions.exit_game()
                        break
                    sleep(1)
                    count -= 1
                break
            if game_health == -1 and last_game_health > 0:
                # won the game and exit game automatically
                self.message_queue.put("CLEAR")
                sleep(8)
                break
            last_game_health = game_health

            self.round = game_functions.get_round()

            # Display the seconds remaining for this phase in real-time.
            self.start_time_of_round = time.time()
            labels = [
                (
                    f"{arena_functions.get_seconds_remaining()}",
                    screen_coords.SECONDS_REMAINING_LOC.get_coords(),
                    -40,
                    -10,
                )
            ]
            self.message_queue.put(("LABEL", labels))
            if (
                settings.FORFEIT
                and perf_counter() - self.start_time > self.forfeit_time
            ):
                game_functions.forfeit()
                continue

            if self.round[0] != ran_round:
                print(
                    f"\n[Comps] Stick to [{','.join(self.comps_manager.current_comp()[1])}] "
                )
                if self.round[0] in game_assets.PORTAL_ROUND:
                    self.portal_round()
                    ran_round: str = self.round[0]
                elif self.round[0] in game_assets.PVP_ROUND:
                    game_functions.default_pos()
                    self.pvp_round()
                    ran_round: str = self.round[0]
                elif self.round[0] in game_assets.PVE_ROUND:
                    game_functions.default_pos()
                    self.pve_round()
                    ran_round: str = self.round[0]
                elif self.round[0] in game_assets.CAROUSEL_ROUND:
                    self.carousel_round()
                    ran_round: str = self.round[0]
                elif self.round[0] in game_assets.SECOND_ROUND:
                    self.second_round()
                    ran_round: str = self.round[0]
                elif self.round[0] in game_assets.ENCOUNTER_ROUNDS:
                    print(f"\n[Encounter Round] {self.round[0]}")
                    print("  Do nothing")
                    self.message_queue.put("CLEAR")
                    self.arena.check_health()
                    ran_round: str = self.round[0]
                if self.round[1] == 1 and self.round[0].split("-")[1] == "1":
                    print("\n[Encounter round setup]")
                    self.encounter_round_setup()
            sleep(0.5)

    def encounter_round_setup(self) -> None:
        """Remove rounds from game_assets and add it back by checking round message"""
        game_assets.CAROUSEL_ROUND = {
            carousel_round
            for carousel_round in game_assets.CAROUSEL_ROUND
            if not carousel_round.startswith(self.round[0].split("-")[0])
        }
        game_assets.PVE_ROUND = {
            pve_round
            for pve_round in game_assets.PVE_ROUND
            if not pve_round.startswith(self.round[0].split("-")[0])
        }
        game_assets.PVP_ROUND = {
            pvp_round
            for pvp_round in game_assets.PVP_ROUND
            if not pvp_round.startswith(self.round[0].split("-")[0])
        }
        game_assets.ANVIL_ROUNDS = {
            anvil_round
            for anvil_round in game_assets.ANVIL_ROUNDS
            if not anvil_round.startswith(self.round[0].split("-")[0])
        }
        game_assets.ITEM_PLACEMENT_ROUNDS = {
            item_placement_round
            for item_placement_round in game_assets.ITEM_PLACEMENT_ROUNDS
            if not item_placement_round.startswith(self.round[0].split("-")[0])
        }
        for index, round_msg in enumerate(game_functions.check_encounter_round()):
            print(f"  Round {self.round[0].split('-')[0]}-{str(index + 1)}: {round_msg.upper()} ROUND")
            if index == 0:
                continue
            if round_msg == "carousel":
                game_assets.CAROUSEL_ROUND.add(
                    self.round[0].split("-")[0] + "-" + str(index + 1)
                )
                game_assets.ANVIL_ROUNDS.add(
                    self.round[0].split("-")[0] + "-" + str(index + 2)
                )
                game_assets.ITEM_PLACEMENT_ROUNDS.add(
                    self.round[0].split("-")[0] + "-" + str(index + 2)
                )
            elif round_msg == "pve":
                game_assets.PVE_ROUND.add(
                    self.round[0].split("-")[0] + "-" + str(index + 1)
                )
            elif round_msg == "pvp":
                game_assets.PVP_ROUND.add(
                    self.round[0].split("-")[0] + "-" + str(index + 1)
                )
            elif round_msg == "encounter":
                game_assets.ENCOUNTER_ROUNDS.add(
                    self.round[0].split("-")[0] + "-" + str(index + 1)
                )
                if index+1 == 2 and 3 <= int(self.round[0].split("-")[0]) <= 4:
                    game_assets.AUGMENT_ROUNDS.add(
                        self.round[0].split("-")[0] + "-" + str(index + 2)
                    )

    def portal_round(self) -> None:
        """Waits for Region Augment decision."""
        print(f"\n[Portal Round] {self.round[0]}")
        self.start_round_tasks()
        sleep(2.5)
        print("  Voting for a portal")
        self.arena.portal_vote()

    def second_round(self) -> None:
        """ "Move unknown champion to board after first carousel."""
        print(f"\n[Second Round] {self.round[0]}")
        self.start_round_tasks()
        while True:
            result = arena_functions.bench_occupied_check()
            if any(result):
                break
        self.arena.bench[result.index(True)] = "?"
        for _ in range(arena_functions.get_level_via_https_request()):
            self.arena.move_unknown()
        sleep(2.5)
        self.arena.portal_augment()
        self.end_round_tasks()

    def carousel_round(self) -> None:
        """Handles tasks for carousel rounds"""
        print(f"\n[Carousel Round] {self.round[0]}")
        self.start_round_tasks()
        if self.round[0] == "3-4":
            self.arena.final_comp = True
        sleep(9.7)
        print("  Getting a champ from the carousel")
        game_functions.get_champ_carousel(self.round[0])

    def pve_round(self) -> None:
        """Handles tasks for PVE rounds."""
        print(f"\n[PvE Round] {self.round[0]}")
        self.start_round_tasks()
        sleep(0.8)
        seconds_in_round = 30
        if self.round[0] in game_assets.AUGMENT_ROUNDS:
            sleep(1)
            self.arena.augment_roll = True
            self.arena.pick_augment()
            sleep(2.5)
            #self.arena.check_dummy()
        if self.round[0] == "1-3":
            sleep(1.5)
            # Check if the active portal is an anvil portal and clear the anvils it if it is
            if self.arena.active_portal in game_assets.ANVIL_PORTALS:
                self.arena.anvil_free[1:] = [True] * 8
                self.arena.clear_anvil()
                self.arena.anvil_free[:2] = [True, False]
                self.arena.clear_anvil()
            self.arena.tacticians_crown_check()
            #self.arena.check_dummy()

        if self.round[0] == "3-7":
            if self.arena.radiant_item is True:
                sleep(1.5)
                self.arena.clear_anvil()

        #if self.round[0] == "4-7":
        #    self.arena.check_dummy()

        self.arena.fix_bench_state()
        self.arena.spend_gold()

        if (
            seconds_in_round - (time.time() - self.start_time_of_round) >= 5.0
        ):  # number picked randomly
            self.arena.move_champions()
        else:
            print("  Less than 5 seconds left in planning. No time to move champions.")
        if (
            seconds_in_round - (time.time() - self.start_time_of_round) >= 5.0
        ):  # number picked randomly
            self.arena.replace_unknown()
        else:
            print(
                "  Less than 5 seconds left in planning. No time to replace unknown units."
            )
        if self.arena.final_comp:
            self.arena.final_comp_check()
        self.arena.bench_cleanup()
        self.end_round_tasks()

    def pvp_round(self) -> None:
        """Handles tasks for PVP rounds."""
        print(f"\n[PvP Round] {self.round[0]}")
        self.start_round_tasks()
        sleep(0.8)
        seconds_in_round = 30
        if self.round[0] in game_assets.AUGMENT_ROUNDS:
            seconds_in_round = 50
            sleep(1)
            self.arena.augment_roll = True
            self.arena.pick_augment()
            sleep(2.5)
            #self.arena.check_dummy()

        if self.fast8_leveling:
            if self.round[0] in game_assets.FAST8_LEVEL_ROUNDS:
                target_level = game_assets.FAST8_LEVEL_ROUNDS[self.round[0]]

                if target_level >= arena_functions.get_level_via_https_request():
                    stop_seconds = 10
                    self.level_up(target_level, stop_seconds)
        else:
            if self.round[0] in game_assets.NORMAL_LEVEL_ROUNDS:
                target_level = game_assets.NORMAL_LEVEL_ROUNDS[self.round[0]]

                if target_level >= arena_functions.get_level_via_https_request():
                    stop_seconds = 10
                    self.level_up(target_level, stop_seconds)

        if self.round[0] in game_assets.PICKUP_ROUNDS:
            print("  Picking up items")
            game_functions.pickup_items()

        self.arena.fix_bench_state()
        self.arena.bench_cleanup()
        if self.round[0] in game_assets.ANVIL_ROUNDS:
            self.arena.clear_anvil()
        self.arena.spend_gold(speedy=self.round[0] in game_assets.PICKUP_ROUNDS)
        if (
            seconds_in_round - (time.time() - self.start_time_of_round) >= 3.0
        ):  # number picked randomly
            self.arena.move_champions()
        else:
            print("  Less than 3 seconds left in planning. No time to move champions.")
        if (
            seconds_in_round - (time.time() - self.start_time_of_round) >= 3.0
        ):  # number picked randomly
            self.arena.replace_unknown()
        else:
            print(
                "  Less than 3 seconds left in planning. No time to replace unknown units."
            )
        if self.arena.final_comp:
            self.arena.final_comp_check()
        self.arena.bench_cleanup()

        if (seconds_in_round - (time.time() - self.start_time_of_round)) >= 3.0 and (
            self.round[0] in game_assets.ITEM_PLACEMENT_ROUNDS
            or arena_functions.get_health() <= 15
            or len(self.arena.items) >= 8
        ):
            self.arena.place_items()
        else:
            print(
                "  Less than 3 seconds left in planning. No time to give items to units."
            )

        self.end_round_tasks()

    def level_up(self, target_level: int, stop_seconds: float) -> None:
        """Level up to the target level, with a maximum duration to avoid being stuck.
        Args:
            target_level (int): Target level to reach.
            stop_seconds (float): Maximum duration for leveling up."""
        prev_level = arena_functions.get_level_via_https_request()
        while arena_functions.get_level_via_https_request() < target_level:
            self.arena.buy_xp_round()
            if time.time() - self.start_time_of_round >= stop_seconds:
                break
        current_level = arena_functions.get_level_via_https_request()

        if current_level > prev_level:
            print(f"  [LEVEL UP] Lvl. {current_level} from Lvl. {prev_level}\n")

    def start_round_tasks(self) -> None:
        """Common tasks across rounds that happen at the start"""
        self.message_queue.put("CLEAR")
        game_functions.default_pos()
        game_functions.default_tactician_pos()
        self.arena.check_health()

    def end_round_tasks(self) -> None:
        """Common tasks across rounds that happen at the end."""
        self.arena.check_health()
        self.arena.get_label()
        game_functions.default_tactician_pos()
        game_functions.default_pos()
