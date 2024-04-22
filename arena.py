"""
Handles the board / bench state inside of the game and
other variables used by the bot to make decisions
"""

from time import sleep
from typing import List, Optional, Union

import arena_functions
import game_assets
import game_functions
import mk_functions
import ocr
import screen_coords
import champion as champion_class
from champion import Champion
from comps import CompsManager


class Arena:
    """Arena class that handles game logic such as board and bench state"""

    # pylint: disable=too-many-instance-attributes,too-many-public-methods,fixme
    def __init__(self, message_queue, comps_manager: CompsManager) -> None:
        self.comps_manager = comps_manager
        self.comps_manager.select_next_comp()
        self.message_queue = message_queue
        self.board_size = 0
        self.bench: List[Optional[Union[Champion, str]]] = [None] * 9
        self.anvil_free: List[bool] = [False] * 9
        self.board: List[Optional[Champion]] = [None] * 28
        self.board_unknown: List[Optional[str]] = []
        self.unknown_slots: List[int] = comps_manager.get_unknown_slots()
        self.board_dummy: List[Optional[str]] = []
        self.champs_to_buy: dict = comps_manager.champions_to_buy()
        self.board_names: List[str] = []
        self.items: List[Optional[str]] = [None] * 10
        self.augments: list = []
        self.final_comp = False
        self.level = 0
        self.augment_roll = True
        self.bench_tacticians_crown = False
        self.tacticians_crown = False
        self.spam_roll = False
        self.active_portal: str = ""
        self.radiant_item = False

    def portal_vote(self) -> None:
        """Picks a portal based on a comp-specific/user-defined portal list
        or defaults to the first portal that is not in the AVOID list"""
        while True:
            sleep(1)
            portals: list = []
            for coords in screen_coords.PORTALS_POS:
                portal: str = ocr.get_text(screenxy=coords.get_coords(), scale=3, psm=7)
                portals.append(portal)
            print(portals)
            if len(portals) == 3 and "" not in portals:
                break

        for potential in game_assets.PORTALS:
            for portal in portals:
                if potential in portal:
                    print(f"  Choosing portal: {portal}")
                    mk_functions.left_click(
                        screen_coords.PORTALS_LOC[portals.index(portal)].get_coords()
                    )
                    sleep(0.7)
                    mk_functions.left_click(
                        screen_coords.PORTALS_VOTES[portals.index(portal)].get_coords()
                    )
                    return

        print(
            "  [!] No priority or backup portal found, undefined behavior may occur for the rest of the round"
        )

        for portal in portals:
            found = False
            for potential in game_assets.AVOID_PORTALS:
                if potential in portal:
                    found = True
                    break
            if not found:
                mk_functions.left_click(
                    screen_coords.PORTALS_LOC[portals.index(portal)].get_coords()
                )
                sleep(0.7)
                mk_functions.left_click(
                    screen_coords.PORTALS_VOTES[portals.index(portal)].get_coords()
                )
                return
        mk_functions.left_click(screen_coords.PORTALS_LOC[0].get_coords())

    def portal_augment(self) -> None:
        """Check the region augment and set flags accordingly"""
        mk_functions.right_click(screen_coords.PORTAL_AUGMENT_LOC.get_coords())
        sleep(1)
        region = ocr.get_text(
            screenxy=screen_coords.PORTAL_AUGMENT_POS.get_coords(), scale=3, psm=7
        )
        self.active_portal = region

        augment_flags = {
            "Artifact Anvil": "Clearing Anvils at round 1-3",
            "Completed Anvil": "Clearing Anvils at round 1-3",
            "Component Anvils": "Clearing Anvils at round 1-3",
            "Support Anvil": "Clearing Anvils at round 1-3",
            "Tome of Traits": "Clearing Anvils at round 1-3",
            "Radiant Item": "Clearing Radiant Item shop at 3-7",
            "Tactician’s Crown": "Collecting Tactician’s Crown at 2-1",
            "Training Dummy": "Checking for target dummy at 1-3",
            "Wandering Trainers": "Checking for target dummy at 1-3",
        }

        augment_name = next((name for name in augment_flags if name in region), None)

        if augment_name:
            flag = augment_flags[augment_name]
            print(f"  Region Augment: {region}. {flag}")
            if augment_name == "Radiant Item":
                self.radiant_item = True
        else:
            print(f"  Region Augment: {region}")

    def fix_bench_state(self) -> None:
        """Iterate through the bench, fix invalid slots, and handle unknown champions"""
        bench_occupied: list = arena_functions.bench_occupied_check()
        for index, slot in enumerate(self.bench):
            if slot is None and bench_occupied[index]:
                # ocr + right click
                mk_functions.right_click(screen_coords.BENCH_LOC[index].get_coords())
                champ_name: str = arena_functions.valid_champ(
                    ocr.get_text(
                        screenxy=screen_coords.PANEL_NAME_LOC.get_coords(),
                        scale=3,
                        psm=7,
                        whitelist=ocr.ALPHABET_WHITELIST
                        + ocr.SPACE_WHITELIST
                        + ocr.SYMBOL_WHITELIST,
                    ),
                    comps=self.comps_manager,
                )
                print(f"Fix bench state: {champ_name}")
                # Replaces "Ilaoi" with "Illaoi"
                if champ_name.strip() == "Ilaoi":
                    champ_name = "Illaoi"
                # Replaces "Xayah & Raka" with "Xayah & Rakan"
                if champ_name.strip() == "Xayah & Raka":
                    champ_name = "Xayah & Rakan"
                if self.champs_to_buy.get(champ_name, 0) > 0:
                    print(
                        f"  The unknown champion {champ_name} exists in comps, keeping it."
                    )
                    traits = self.comps_manager.champions[champ_name]
                    trait1 = traits["Trait1"]
                    trait2 = traits["Trait2"]
                    trait3 = traits["Trait3"]
                    self.bench[index] = champion_class.create_default_champion(
                        champ_name,
                        index,
                        True,
                        self.comps_manager,
                        trait1,
                        trait2,
                        trait3,
                        0,
                    )
                    self.champs_to_buy[champ_name] -= 1
                else:
                    print(
                        f"  Selling the unknown champion {champ_name}. Does not exist in comps."
                    )
                    self.bench[index] = "?"
                continue
            if isinstance(slot, str) and not bench_occupied[index]:
                self.bench[index] = None
                continue
            if isinstance(slot, Champion) and not bench_occupied[index]:
                self.bench[index] = None

    def bought_champion(self, name: str, slot: int) -> None:
        """Purchase a champion and create a Champion instance"""
        self.bench[slot] = Champion(
            name=name,
            coords=screen_coords.BENCH_LOC[slot].get_coords(),
            build=self.comps_manager.current_comp()[1][name]["items"].copy(),
            build2=self.comps_manager.current_comp()[1][name]["recommendItems"].copy(),
            item_slots_filled=0,
            slot=slot,
            size=self.comps_manager.champions[name]["Board Size"],
            final_comp=self.comps_manager.current_comp()[1][name]["final_comp"],
            trait1=self.comps_manager.champions[name]["Trait1"],
            trait2=self.comps_manager.champions[name]["Trait2"],
            trait3=self.comps_manager.champions[name]["Trait3"],
        )
        mk_functions.move_mouse(screen_coords.DEFAULT_LOC.get_coords())
        sleep(0.5)
        self.fix_bench_state()

    def have_champion(self) -> Champion | None:
        """Check if there is a champion on the bench that is not on the board"""
        return next(
            (
                champion
                for champion in self.bench
                if isinstance(champion, Champion)
                and champion.name not in self.board_names
            ),
            None,
        )

    def move_known(self, champion: Champion) -> None:
        """Moves a known champion to the board"""
        print(f"  Moving {champion.name} to board")
        destination: tuple = screen_coords.BOARD_LOC[
            self.comps_manager.current_comp()[1][champion.name]["board_position"]
        ].get_coords()
        mk_functions.left_click(champion.coords)
        sleep(0.18)
        mk_functions.left_click(destination)
        champion.coords = destination
        self.board.append(champion)
        self.board_names.append(champion.name)
        self.bench[self.bench.index(champion)] = None
        champion.index = self.comps_manager.current_comp()[1][champion.name][
            "board_position"
        ]
        self.board_size += champion.size

    def move_unknown(self) -> None:
        """Moves unknown champion to the board"""
        for index, champion in enumerate(self.bench):
            if isinstance(champion, str):
                print(f"  Moving {champion} to board")
                mk_functions.left_click(screen_coords.BENCH_LOC[index].get_coords())
                sleep(0.1)
                mk_functions.left_click(
                    screen_coords.BOARD_LOC[
                        self.unknown_slots[len(self.board_unknown)]
                    ].get_coords()
                )
                self.bench[index] = None
                self.board_unknown.append(champion)
                self.board_size += 1
                return

    def sell_bench(self) -> None:
        """Sells all of the champions on the bench"""
        for index, name in enumerate(self.bench):
            print(f"  Selling {name}")
            mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
            self.bench[index] = None

    def unknown_in_bench(self) -> bool:
        """Sells all of the unknown champions on the bench"""
        return any(isinstance(slot, str) for slot in self.bench)

    def move_champions(self) -> None:
        """Moves champions to the board"""
        self.level: int = arena_functions.get_level_via_https_request()
        while self.level > self.board_size:
            champion: Champion | None = self.have_champion()
            if champion is not None:
                self.move_known(champion)
            elif self.unknown_in_bench():
                self.move_unknown()
            else:
                bought_unknown = False
                shop: list = arena_functions.get_shop(self.comps_manager)
                for champion in shop:
                    gold: int = arena_functions.get_gold()
                    valid_champ: bool = (
                        champion[1] in self.comps_manager.champions
                        and self.comps_manager.champion_gold_cost(champion[1]) <= gold
                        and self.comps_manager.champion_board_size(champion[1]) == 1
                        and self.champs_to_buy.get(champion[1], -1) < 0
                        and champion[1] not in self.board_unknown
                    )
                    if valid_champ:
                        none_slot: int = arena_functions.empty_slot()
                        mk_functions.left_click(
                            screen_coords.BUY_LOC[champion[0]].get_coords()
                        )
                        sleep(0.2)
                        self.bench[none_slot] = f"{champion[1]}"
                        self.move_unknown()
                        bought_unknown = True
                        break

                if not bought_unknown:
                    print("  Need to sell entire bench to keep track of board")
                    self.sell_bench()
                    return

    def replace_unknown(self) -> None:
        """Replaces unknown champion"""
        champion: Champion | None = self.have_champion()
        if len(self.board_unknown) > 0 and champion is not None:
            mk_functions.press_e(
                screen_coords.BOARD_LOC[
                    self.unknown_slots[len(self.board_unknown) - 1]
                ].get_coords()
            )
            self.board_unknown.pop()
            self.board_size -= 1
            self.move_known(champion)

    def bench_cleanup(self) -> None:
        """Sells unknown champions"""
        self.anvil_free: list[bool] = [False] * 9
        for index, champion in enumerate(self.bench):
            if champion == "?" or isinstance(champion, str):
                print("  Selling unknown champion")
                mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
                self.bench[index] = None
                self.anvil_free[index] = True
            elif isinstance(champion, Champion):
                if (
                    self.champs_to_buy.get(champion.name, -1) < 0
                    and champion.name in self.board_names
                ):
                    print("  Selling unknown champion")
                    mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
                    self.bench[index] = None
                    self.anvil_free[index] = True

    def clear_anvil(self) -> None:
        """Clears anvil on the bench, selects middle item"""
        for index, champion in enumerate(self.bench):
            if champion is None and not self.anvil_free[index]:
                mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
        sleep(0.8)
        anvil_msg: str = ocr.get_text(
            screenxy=screen_coords.ANVIL_MSG_POS.get_coords(),
            scale=3,
            psm=7,
            whitelist=ocr.ALPHABET_WHITELIST + ocr.SPACE_WHITELIST,
        )
        if anvil_msg in ["Choose One", "Choose Your Path", "Feeling lucky"]:
            print("clearing anvil")
            sleep(1)
            mk_functions.left_click(screen_coords.BUY_LOC[2].get_coords())
        sleep(1)

    def get_random_final_comp_champ_on_board_with_no_build(self) -> Champion | None:
        print("    Looking for a random champ that we don't want to build items.")
        for champ in self.board:
            if isinstance(champ, Champion):
                if len(champ.build) == 0:
                    print(
                        f"      {champ.name} is a unit that we haven't specified items for."
                    )
                    return champ
        return None

    def place_items(self) -> None:
        """Loops through the champs first so that we can add multiple items to one champ first,
        before moving onto the next champ."""
        print("  Placing items on champs")
        self.items = arena_functions.get_items()
        print(f"  Items: {list(filter(None.__ne__, self.items))}")
        champs_on_board_sorted_by_items: list[Champion] = (
            self.get_list_of_champs_on_board_in_order_of_amount_of_total_items()
        )
        for champ in champs_on_board_sorted_by_items:
            if isinstance(champ, Champion):
                # try to give completed items first
                # for loop like this because a champ can have 3 complete/non-component items
                print(
                    f"    Champ: {champ.name}, # of Item Slots Filled: {champ.item_slots_filled}, Items: {champ.items}"
                )
                combined_two_items = False
                for _ in range(champ.item_slots_filled, 6):
                    # can't give completed items if there aren't two slots or more available
                    if champ.item_slots_filled < 5:
                        self.add_ornn_item_to_champ(champ)
                        self.add_radiant_version_of_items_to_champ(champ)
                        self.add_completed_item_to_champ(champ)
                        self.add_support_item_to_champ(champ)
                        self.add_trait_item_to_champ(champ)
                        self.add_tacticians_crown_to_champ(champ)
                        self.check_for_gloves()
                        self.check_if_we_should_spam_sparring_gloves()
                        self.add_random_completed_item_to_champ(champ)
                    if champ.item_slots_filled % 2 == 0:
                        combined_two_items = self.add_any_item_from_combining_two_component_items_on_champ(
                            champ
                        )
                        if self.can_give_champ_a_completed_secondary_item(champ):
                            combined_two_items = (
                                combined_two_items
                                or self.add_any_secondary_item_from_combining_two_component_items_on_champ(
                                    champ
                                )
                            )
                if not combined_two_items:
                    print(f"            Unable to complete an item for {champ.name}.")
                # Items removers can be used any number of times on one unit.
                self.throwaway_reforger_item(champ)
                self.throwaway_magnetic_remover_item(champ)
                self.use_champion_duplicators(champ)
                self.use_masterwork_upgrade(champ)

    def add_one_item_to_champ(
        self, champ: Champion, items_bench_index: int, consumable: bool = False
    ):
        """Move the item from its location on the board to the champ.
        Prints out the name of the item and the champ it was placed on.
        Adds it to the champs list of items it has.
        Removes the instance of the item from the board's list of items."""
        item = self.items[items_bench_index]
        arena_functions.move_item(
            screen_coords.ITEM_POS[items_bench_index][0].get_coords(), champ.coords
        )
        arena_functions.print_item_placed_on_champ(item, champ)
        if not consumable:
            champ.item_slots_filled += 1
            champ.items.append(item)
        self.items[items_bench_index] = None

    def add_completed_item_to_champ(self, champ: Champion) -> None:
        """If we have completed items waiting on the bench,
        that are the unit's 'best_in_slot' (BIS items) give them to the unit."""
        for _, completed_item in enumerate(champ.build):
            if completed_item in self.items:
                self.add_one_item_to_champ(champ, self.items.index(completed_item))
                champ.build.remove(completed_item)
                champ.non_component_items.append(completed_item)
                champ.item_slots_filled += 1
        return

    def add_random_completed_item_to_champ(self, champ: Champion) -> None:
        """If the champion doesn't have any items in champ.build,
        add the first available completed item from game_assets.FORCED_ITEMS."""
        for full_item in game_assets.FORCED_ITEMS:
            if full_item in self.items and not champ.build:
                self.add_one_item_to_champ(champ, self.items.index(full_item))
                champ.non_component_items.append(full_item)
                champ.item_slots_filled += 1
        return

    def add_radiant_version_of_items_to_champ(self, champ: Champion) -> None:
        """If we have radiant items waiting on the bench,
        that are a better version of the champ's completed items it WANTS to build
        give them to the champ."""
        for radiant_item, completed_item in game_assets.RADIANT_ITEMS_DICT.items():
            if completed_item in champ.build and radiant_item in self.items:
                self.add_one_item_to_champ(champ, self.items.index(radiant_item))
                champ.build.remove(completed_item)
                champ.non_component_items.append(radiant_item)
        return

    def add_ornn_item_to_champ(self, champ: Champion) -> None:
        """If there is an Ornn item on the bench that this champ wants, give it to 'em."""
        for ornn_item in game_assets.ARTIFACT_ITEMS:
            if ornn_item in self.items:
                if (
                    ornn_item == "BlacksmithsGloves"
                    and not champ.build
                    and champ.item_slots_filled <= 0
                ):
                    self.add_one_item_to_champ(champ, self.items.index(ornn_item))
                    champ.non_component_items.append(ornn_item)
                    champ.item_slots_filled += (
                        5  # Increment by 5 to make it a total of 6
                    )
                elif ornn_item in champ.build:
                    self.add_one_item_to_champ(champ, self.items.index(ornn_item))
                    champ.build.remove(ornn_item)
                    champ.non_component_items.append(ornn_item)
                    champ.item_slots_filled += 1
                elif not champ.build:
                    champ.build = [ornn_item]
                    self.add_one_item_to_champ(champ, self.items.index(ornn_item))
                    champ.build.remove(ornn_item)
                    champ.non_component_items.append(ornn_item)
                    champ.item_slots_filled += 1
        return

    def add_support_item_to_champ(self, champ: Champion) -> None:
        """If there is a Support item on the bench that this champ wants, give it to 'em."""
        for support_item in game_assets.SUPPORT_ITEMS:
            if support_item in self.items:
                if support_item in champ.build:
                    self.add_one_item_to_champ(champ, self.items.index(support_item))
                    champ.build.remove(support_item)
                    champ.non_component_items.append(support_item)
                    champ.item_slots_filled += 1
                elif not champ.build:
                    champ.build = [support_item]
                    self.add_one_item_to_champ(champ, self.items.index(support_item))
                    champ.build.remove(support_item)
                    champ.non_component_items.append(support_item)
                    champ.item_slots_filled += 1
        return

    def add_trait_item_to_champ(self, champ: Champion) -> None:
        """If there is a trait emblem item on the bench that this champ wants and doesn't have, give it to 'em."""
        for trait_item in (
            game_assets.CRAFTABLE_EMBLEM_ITEMS | game_assets.ELUSIVE_EMBLEM_ITEMS
        ):
            if trait_item in self.items:
                # Check if the champion already has the trait associated with the trait emblem item
                if not champ.check_trait(trait_item):
                    if trait_item in champ.build:
                        self.add_one_item_to_champ(champ, self.items.index(trait_item))
                        champ.build.remove(trait_item)
                        champ.non_component_items.append(trait_item)
                        champ.item_slots_filled += 1
                    elif not champ.build:
                        self.add_one_item_to_champ(champ, self.items.index(trait_item))
                        champ.non_component_items.append(trait_item)
                        champ.item_slots_filled += 1
        return

    def add_tacticians_crown_to_champ(self, champ: Champion) -> None:
        """If there is a Tactician's Crown on the bench then change board size and give to champ."""
        if "TacticiansCrown" in self.items:
            self.bench_tacticians_crown = True
            if not self.tacticians_crown:
                print("  Tacticians Crown on bench, adding extra slot to board")
                self.board_size -= 1
                self.tacticians_crown = True
            self.move_champions()
            if not champ.build and champ.item_slots_filled <= 0:
                self.add_one_item_to_champ(champ, self.items.index("TacticiansCrown"))
                champ.non_component_items.append("TacticiansCrown")
                champ.item_slots_filled += 1

    def check_for_gloves(self) -> bool:
        """Check if Lucky Gloves should be made, prioritize adding glove items to a champion."""
        gloves = [
            "ThiefsGloves",
            "BlacksmithsGloves",
            "RascalsGloves",
            "AccomplicesGloves",
        ]

        # Check if any glove items are available
        glove_item = next((glove for glove in gloves if glove in self.items), None)

        if glove_item:
            # If glove item is available, add it to a champion
            no_build_champ = self.get_random_final_comp_champ_on_board_with_no_build()
            if no_build_champ is not None and no_build_champ.item_slots_filled <= 0:
                if self.add_gloves_to_champ(no_build_champ, glove_item):
                    return True

        # Check if Lucky Gloves augment is present and add them if necessary
        if "Lucky Gloves" in self.augments:
            print("We have Lucky Gloves!")
            no_build_champ = self.get_random_final_comp_champ_on_board_with_no_build()
            if no_build_champ is not None and no_build_champ.item_slots_filled <=0:
                if self.add_gloves_to_champ(no_build_champ):
                    return True

        return False

    def check_if_we_should_spam_sparring_gloves(self) -> bool:
        """Checks if our health is at 30 or less and then calls the function to spam thief's gloves."""
        health: int = arena_functions.get_health()
        if health <= 30:
            for champ in self.board:
                if isinstance(champ, Champion):
                    if len(champ.build) <= 0 and champ.item_slots_filled <= 0:
                        if self.add_gloves_to_champ(champ):
                            return True
        return False

    def add_gloves_to_champ(self, champ: Champion, glove_item: str = None) -> bool:
        """Makes Thiefs Gloves if possible and gives them to a champ with no items."""
        # print("    Attempting to add Thief's Gloves to a random itemless champ.")
        gloves_index_1 = -1
        gloves_index_2 = -1

        if glove_item:
            # Give the specified glove item to the champion
            if glove_item in self.items:
                gloves_index = self.items.index(glove_item)
                arena_functions.move_item(
                    screen_coords.ITEM_POS[gloves_index][0].get_coords(), champ.coords
                )
                print(f"      Placed {self.items[gloves_index]} on {champ.name}")
                self.items[gloves_index] = None
                champ.item_slots_filled += 6
                return True
            else:
                print(f"    {glove_item} not found in inventory.")
                return False

        for index, _ in enumerate(self.items):
            if self.items[index] == "SparringGloves":
                if gloves_index_1 == -1:
                    print("    Found Sparring Gloves #1 for a Thief's Gloves.")
                    gloves_index_1 = index
                if gloves_index_1 != -1 and gloves_index_2 == -1:
                    print("    Found Sparring Gloves #2 for a Thief's Gloves.")
                    gloves_index_2 = index
                    break
        if (
            gloves_index_1 != -1
            and gloves_index_2 != -1
            and gloves_index_1 != gloves_index_2
        ):
            print("    We have 2 Sparring Gloves to make Thief's Gloves with!")
            arena_functions.move_item(
                screen_coords.ITEM_POS[gloves_index_1][0].get_coords(), champ.coords
            )
            print(f"      Placed {self.items[gloves_index_1]} on {champ.name}")
            self.items[gloves_index_1] = None
            arena_functions.move_item(
                screen_coords.ITEM_POS[gloves_index_2][0].get_coords(), champ.coords
            )
            print(f"      Placed {self.items[gloves_index_2]} on {champ.name}")
            self.items[gloves_index_2] = None
            champ.item_slots_filled += 6
            return True
        return False

    def add_consumable_item_to_champ(self, champ: Champion, items_bench_index: int):
        """Simply calls the self.add_one_item_to_champ() function with a consumable value of True."""
        self.add_one_item_to_champ(champ, items_bench_index, True)

    def throwaway_reforger_item(self, champ: Champion) -> bool:
        """Simply tries to use a Reforger on a champ with 1 component item.
        Returns True if we used it."""
        if "Reforger" in self.items:
            if champ.item_slots_filled == 1:
                self.add_consumable_item_to_champ(champ, self.items.index("Reforger"))
                champ.item_slots_filled -= 1
                for item in champ.current_building:
                    champ.current_building.remove(item)
                    print(
                        f"    {champ.name} is no longer trying to build {champ.current_building} due to a Reforger."
                    )
                if champ.component_item != "":
                    print(
                        f"    A Reforger removed {champ.component_item} from {champ.name} and changed it into a new item."
                    )
                else:
                    print(
                        "    [!] We removed a component item from a champ, but we didn't know what component it was!"
                    )
                return True
            else:
                print(
                    "  Tried to throw away a Reforger on a nearly-itemless champ, "
                    "but couldn't find a nearly itemless champ."
                )
                return False
        return False

    def throwaway_magnetic_remover_item(self, champ: Champion) -> bool:
        """Simply tries to use a Magnetic Remover on a champ with 1 component items.
        Returns True if we used it."""
        if "MagneticRemover" in self.items:
            if champ.item_slots_filled == 1:
                self.add_consumable_item_to_champ(
                    champ, self.items.index("MagneticRemover")
                )
                champ.item_slots_filled -= 1
                # Removes the tuple of (completed_item, needed_component_item) that the champ had.
                for item in champ.current_building:
                    champ.current_building.remove(item)
                    print(
                        f"    {champ.name} is no longer trying to build {champ.current_building} due to a Magnetic Remover."
                    )
                if champ.component_item != "":
                    print(
                        f"    A Magnetic Remover removed {champ.component_item} from {champ.name}."
                    )
                else:
                    print(
                        "    [!] We removed a component item from a champ, but we didn't know what component it was!"
                    )
                return True
            else:
                print(
                    "  Tried to throw away a Magnetic Remover on a nearly-itemless champ, "
                    "but couldn't find a nearly itemless champ."
                )
                return False
        return False

    def is_possible_to_combine_two_components_into_given_item(
        self, champ: Champion, complete_item: str
    ) -> bool:
        """Assumes that the complete item in the champ's build, exists as a CRAFTABLE item.
        Returns a boolean value that represent if BOTH component items for a complete item exist in self.items.
        """
        if complete_item not in champ.build:
            # print(f"        {complete_item} is not in  {champ.name}'s build.")
            return False
        if complete_item not in game_assets.CRAFTABLE_ITEMS_DICT:
            print(f"    You have misspelled {complete_item}.")
            return False
        copy_of_owned_items = self.items.copy()
        for item in game_assets.CRAFTABLE_ITEMS_DICT[complete_item]:
            if item not in copy_of_owned_items:
                # print(f"        We are missing a {item} to build the {complete_item}.")
                return False
            else:  # make sure for items that need duplicate component items, this doesn't count one component twice
                # print(f"        Removing the {item} from the copy of owned items, because we don't want to count items twice.")
                copy_of_owned_items.remove(item)
        return True

    def get_item_that_is_possible_to_combine_from_components(
        self, champ: Champion
    ) -> str | None:
        """Searches through the champ's BIS items it wants to build and returns the complete BIS item
        if it can be crafted from component items currently on the bench."""
        for complete_item in champ.build:
            # print(f"      For {complete_item} in {champ.name}'s build.")
            if self.is_possible_to_combine_two_components_into_given_item(
                champ, complete_item
            ):
                # print(f"        It is possible to create the {complete_item} for {champ}.")
                return complete_item
            else:
                # print(f"        It is not possible to craft the {complete_item} for {champ}.")
                continue
        return None

    def add_any_item_from_combining_two_component_items_on_champ(
        self, champ: Champion
    ) -> bool:
        """Assumes that the champ has no component items on them.
        Gets any Best In Slot (BIS) craftable item from the champ
        that we have determined we have both components for.
        Then adds both components to the champ to create a completed item."""
        complete_item = self.get_item_that_is_possible_to_combine_from_components(champ)
        if complete_item is not None:
            # print(f"      Creating complete item: {complete_item} for {champ.name}.")
            component_one = game_assets.CRAFTABLE_ITEMS_DICT[complete_item][0]
            component_two = game_assets.CRAFTABLE_ITEMS_DICT[complete_item][1]
            self.add_one_item_to_champ(champ, self.items.index(component_one))
            self.add_one_item_to_champ(champ, self.items.index(component_two))
            champ.non_component_items.append(complete_item)
            champ.build.remove(complete_item)
            # Just make sure we don't give them the same item twice.
            if complete_item in champ.secondary_items:
                champ.secondary_items.remove(complete_item)
            return True
        return False

    # TODO: combine this with the bis functions into one function that takes in the list of items to check
    def is_possible_to_combine_two_components_into_given_secondary_item(
        self, champ: Champion, complete_item: str
    ) -> bool:
        """Assumes that the complete item in the champ's build, exists as a CRAFTABLE item.
        Returns a boolean value that represent if BOTH component items for a complete item exist in self.items.
        """
        if complete_item not in champ.secondary_items:
            return False
        copy_of_owned_items = self.items.copy()
        for item in game_assets.CRAFTABLE_ITEMS_DICT[complete_item]:
            if item not in copy_of_owned_items:
                return False
            else:  # makes sure for items that need duplicate component items, this doesn't count one component twice
                copy_of_owned_items.remove(item)
        return True

    # TODO: combine this with the bis functions into one function that takes in the list of items to check
    def get_secondary_item_that_is_possible_to_combine_from_components(
        self, champ: Champion
    ) -> str | None:
        """Searches through the champ's BIS items it wants to build and returns the complete BIS item
        if it can be crafted from component items currently on the bench."""
        for complete_item in champ.secondary_items:
            if self.is_possible_to_combine_two_components_into_given_secondary_item(
                champ, complete_item
            ):
                return complete_item
            else:
                return None
        return

    # TODO: combine this with the bis functions into one function that takes in the list of items to check
    def add_any_secondary_item_from_combining_two_component_items_on_champ(
        self, champ: Champion
    ) -> bool:
        """Assumes that the champ has no component items on them.
        Gets any Best In Slot (BIS) craftable item from the champ
        that we have determined we have both components for.
        Then adds both components to the champ to create a completed item."""
        complete_item = (
            self.get_secondary_item_that_is_possible_to_combine_from_components(champ)
        )
        if complete_item is not None:
            print(
                f"      Creating complete secondary item: {complete_item} for {champ.name}."
            )
            component_one = game_assets.CRAFTABLE_ITEMS_DICT[complete_item][0]
            component_two = game_assets.CRAFTABLE_ITEMS_DICT[complete_item][1]
            self.add_one_item_to_champ(champ, self.items.index(component_one))
            self.add_one_item_to_champ(champ, self.items.index(component_two))
            champ.non_component_items.append(complete_item)
            champ.secondary_items.remove(complete_item)
            # Just make sure we don't give them the same item twice.
            if complete_item in champ.build:
                champ.build.remove(complete_item)
            return True
        return False

    def get_list_of_champs_on_board_in_order_of_amount_of_total_items(
        self,
    ) -> list[Champion]:
        """Returns a list of Champion objects that are on the board,
        ordered by how many items they have listed in BIS, in descending order.
        Extremely unlikely, but the list might return as empty."""
        champs_on_board_dict = {}
        for champ in self.board:
            if isinstance(champ, Champion):
                if champ.name in self.comps_manager.current_comp()[1]:
                    champ_in_comp = self.comps_manager.current_comp()[1][champ.name]
                    champs_on_board_dict[champ] = len(champ_in_comp["items"])
        # using just Champion.build would mean that when a unit builds an item, they receive less priority
        return sorted(champs_on_board_dict, key=champs_on_board_dict.get, reverse=True)

    def get_index_of_one_lesser_champion_duplicators_on_bench(self) -> int | None:
        if "LesserChampionDuplicator" in self.items:
            return self.items.index("LesserChampionDuplicator")
        else:
            return None

    def get_index_of_one_champion_duplicators_on_bench(self) -> int | None:
        if "ChampionDuplicator" in self.items:
            return self.items.index("ChampionDuplicator")
        else:
            return None

    def use_champion_duplicators(self, champ: Champion) -> None:
        """Uses Champion Duplicators on champs.
        Makes a list of all champs that are on the board and that still need to be bought to be raised
        to the desire star level. Sorts that list of champs, by the amount of items they need, in descending order
        so that we duplicate most important champions first.
        Will only use non-lesser champion duplicators on champs that cost 4 or 5."""
        # print("    Looking for champion duplicators.")
        lesser_duplicator_index = (
            self.get_index_of_one_lesser_champion_duplicators_on_bench()
        )
        normal_duplicator_index = self.get_index_of_one_champion_duplicators_on_bench()
        # Exit the function sooner if we don't have any champion duplicators
        if lesser_duplicator_index is None and normal_duplicator_index is None:
            return
        print("    We have champion duplicators to use.")
        if (
            champ.name in self.champs_to_buy
            and champ.name in self.comps_manager.champions
        ):
            unit_dict = self.comps_manager.champions[champ.name]
            # print(f"      Champ Dict: {champ_dict}")
            cost = unit_dict["Gold"]
            # print(f"        Cost: {cost}")
            if cost <= 3 and lesser_duplicator_index is not None:
                self.add_one_item_to_champ(champ, lesser_duplicator_index, True)
            elif cost > 3 and normal_duplicator_index is not None:
                self.add_one_item_to_champ(champ, normal_duplicator_index, True)
        return

    def use_masterwork_upgrade(self, champ: Champion) -> None:
        """Uses a Masterwork Upgrade on a champ.
        Uses it on the first champ with the most BIS items, since the item upgrades craftable completed items
        to Radiant versions. This will fail if the champ isn't holding any completed items.
        This function doesn't select the item from the Armory shop."""
        # print("    Try using Masterwork Upgrade.")
        if "MasterworkUpgrade" not in self.items:
            return
        if len(champ.non_component_items) > 0:
            self.add_one_item_to_champ(champ, self.items.index("MasterworkUpgrade"))

    # TODO: Clean this up and break down into smaller functions.
    # TODO: Possibly should change it to give the rest of the component items before giving emblem and support items.
    def add_random_items_on_strongest_champs_at_one_loss_left(self):
        """This function tries to add all the leftover items on the board before the bot loses the game.
        It focuses on placing items onto the most important champs, as defined by how many BIS items they have in their comp file.
        It will place the strongest items first (e.g. Ornn Artifact Items and Radiant Items).
        Then place the normal completed items, because it's most likely those will help the damage-dealing carries the most.
        Then emblem items and support items. Hopefully by the time we are placing those items
        we are giving them to non-carries that will buff the carries.
        Then we take the remaining component items and try to give them too.
        """
        if arena_functions.get_health() > 36:
            return
        print("  Randomly adding items to our carry champs since we are about to lose.")
        champs_on_board_sorted_by_items: list[Champion] = (
            self.get_list_of_champs_on_board_in_order_of_amount_of_total_items()
        )
        for champ in champs_on_board_sorted_by_items:
            if champ.item_slots_filled >= 6:
                print(
                    f"    Champ: {champ.name} has an item_slots_filled value of {champ.item_slots_filled}. Continuing..."
                )
                continue
            # Give non-component items first.
            if champ.item_slots_filled % 2 == 0:
                print(
                    "    END GAME: Looking to add Ornn, Radiant, Completed, Emblem, Support Items."
                )
                # Try to place Ornn and Radiant items first
                items_to_place = game_assets.ARTIFACT_ITEMS | game_assets.RADIANT_ITEMS
                for item in items_to_place:
                    if item == "BlacksmithsGloves" and item in self.items and champ.item_slots_filled <= 0:
                        self.add_one_item_to_champ(champ, self.items.index(item))
                        champ.non_component_items.append(item)
                        champ.item_slots_filled += 5
                    elif item in self.items and champ.item_slots_filled < 6:
                        self.add_one_item_to_champ(champ, self.items.index(item))
                        champ.non_component_items.append(item)
                        if item in champ.build:
                            champ.build.remove(item)
                        if item in champ.secondary_items:
                            champ.secondary_items.remove(item)
                        champ.item_slots_filled += 1
                # Then try to place completed items
                items_to_place = game_assets.COMBINED_ITEMS
                for item in items_to_place:
                    if item == "ThiefsGloves" and item in self.items and champ.item_slots_filled <= 0:
                        self.add_one_item_to_champ(champ, self.items.index(item))
                        champ.non_component_items.append(item)
                        champ.item_slots_filled += 5
                    if item in self.items and champ.item_slots_filled < 6:
                        self.add_one_item_to_champ(champ, self.items.index(item))
                        champ.non_component_items.append(item)
                        if item in champ.build:
                            champ.build.remove(item)
                        if item in champ.secondary_items:
                            champ.secondary_items.remove(item)
                        champ.item_slots_filled += 2
                # Place emblem items
                items_to_place = game_assets.CRAFTABLE_EMBLEM_ITEMS | game_assets.ELUSIVE_EMBLEM_ITEMS
                for item in items_to_place:
                    if item in self.items and champ.item_slots_filled < 6:
                        if not champ.check_trait(item):
                            self.add_one_item_to_champ(champ, self.items.index(item))
                            champ.non_component_items.append(item)
                            if item in champ.build:
                                champ.build.remove(item)
                            champ.item_slots_filled += 1
                # Place support items
                for item in game_assets.SUPPORT_ITEMS:
                    if item in self.items and champ.item_slots_filled < 6:
                        self.add_one_item_to_champ(champ, self.items.index(item))
                        champ.non_component_items.append(item)
                        if item in champ.build:
                            champ.build.remove(item)
                        champ.item_slots_filled += 1
            # Place component items
            items_to_place = game_assets.COMPONENT_ITEMS
            for item in items_to_place:
                if item in self.items:
                    print("    END GAME: Looking to add component items.")
                    if champ.item_slots_filled % 2 == 0:
                        champ.component_item = item
                    else:
                        for current_building in champ.current_building:
                            print(f"    The champ {champ.name} was trying to build a {current_building}")
                            print(f"      But we gave them a {item} component item instead.")
                            champ.current_building.remove(champ.current_building)
                        champ.component_item = ""
                        if len(champ.items) != 0:
                            champ.items.pop()
                    self.add_one_item_to_champ(champ, self.items.index(item))

    def fix_unknown(self) -> None:
        """Checks if the item passed in arg one is valid"""
        sleep(0.25)
        mk_functions.press_e(
            screen_coords.BOARD_LOC[self.unknown_slots[0]].get_coords()
        )
        if len(self.board_unknown) > 0:
            self.board_unknown.pop(0)
            self.board_size -= 1

    def remove_champion(self, champion: Champion) -> None:
        """Remove a champion from the board and update relevant attributes"""
        for index, slot in enumerate(self.bench):
            if isinstance(slot, Champion) and slot.name == champion.name:
                mk_functions.press_e(slot.coords)
                self.bench[index] = None

        # Remove all instances of champion in champs_to_buy
        if champion.name in self.champs_to_buy:
            self.champs_to_buy.pop(champion.name)

        mk_functions.press_e(champion.coords)
        self.board_names.remove(champion.name)
        self.board_size -= champion.size
        self.board.remove(champion)

    def final_comp_check(self) -> None:
        """Check the board and replace champions not in the final composition"""
        for slot in self.bench:
            if (
                isinstance(slot, Champion)
                and slot.final_comp
                and slot.name not in self.board_names
            ):
                for champion in self.board:
                    if isinstance(champion, Champion):
                        if not champion.final_comp and champion.size == slot.size:
                            print(f"  Replacing {champion.name} with {slot.name}")
                            self.remove_champion(champion)
                            self.move_known(slot)
                            break

    def tacticians_crown_check(self) -> None:
        """Checks if the item from carousel is tacticians crown"""
        mk_functions.move_mouse(screen_coords.ITEM_POS[0][0].get_coords())
        sleep(0.5)
        item: str = ocr.get_text(
            screenxy=screen_coords.ITEM_POS[0][1].get_coords(),
            scale=3,
            psm=7,
            whitelist=ocr.ALPHABET_WHITELIST,
        )
        item: str = arena_functions.valid_item(item)
        try:
            if "TacticiansCrown" in item:
                print("  Tacticians Crown on bench, adding extra slot to board")
                self.bench_tacticians_crown = True
                if not self.tacticians_crown:  # Check if adjustment is needed
                    self.board_size -= 1
                    self.tacticians_crown = True

            else:
                print(f"{item} is not TacticiansCrown")
        except TypeError:
            print("  Item could not be read for Tacticians Check")

    def spend_gold(self, speedy=False) -> None:
        """Spend gold to buy champions and XP"""
        first_run = True
        min_gold = 100 if speedy else (20 if self.spam_roll else 52)
        while first_run or arena_functions.get_gold() >= min_gold:
            if not first_run:
                current_level = arena_functions.get_level_via_https_request()
                if current_level != 10:
                    mk_functions.buy_xp()
                    print("  Purchasing XP")
                mk_functions.reroll()
                print("  Rerolling shop")
                sleep(0.1)
            shop: list = arena_functions.get_shop(self.comps_manager)

            # For set 11 encounter round shop delay and choose items popup
            for _ in range(15):
                if speedy:
                    break
                if all(champ[1] == "" for champ in shop):
                    print("  Waiting encounter round animation ends")
                    sleep(1)
                    anvil_msg: str = ocr.get_text(
                        screenxy=screen_coords.ANVIL_MSG_POS.get_coords(),
                        scale=3,
                        psm=7,
                        whitelist=ocr.ALPHABET_WHITELIST + ocr.SPACE_WHITELIST,
                    )
                    if anvil_msg in ["Choose One", "Choose Your Path", "Feeling lucky"]:
                        sleep(2)
                        print("  Choosing item")
                        mk_functions.left_click(screen_coords.BUY_LOC[2].get_coords())
                        sleep(0.2)
                        mk_functions.left_click(screen_coords.BUY_LOC[1].get_coords())
                        sleep(1.5)
                        shop: list = arena_functions.get_shop(self.comps_manager)
                        break
                    # For set 11 re-fetch shop after item choice
                    shop: list = arena_functions.get_shop(self.comps_manager)
                else:
                    break

            print(f"  Shop: {shop}")
            for champion in shop:
                if (
                    self.champs_to_buy.get(champion[1], -1) >= 0
                    and arena_functions.get_gold()
                    - self.comps_manager.champions[champion[1]]["Gold"]
                    >= 0
                ):
                    self.buy_champion(champion, 1)
            first_run = False

    def buy_champion(self, champion, quantity) -> None:
        """Buy champion in shop"""
        none_slot: int = arena_functions.empty_slot()
        if none_slot != -1:
            buy_coords = screen_coords.BUY_LOC[champion[0]].get_coords()
            mk_functions.left_click(buy_coords)
            print(f"Purchased {champion[1]}")
            self.bought_champion(champion[1], none_slot)
            if champion[1] in self.champs_to_buy:
                self.champs_to_buy[champion[1]] -= quantity
        else:
            print(f"Board is full but want {champion[1]}")
            buy_coords = screen_coords.BUY_LOC[champion[0]].get_coords()
            mk_functions.left_click(buy_coords)
            game_functions.default_pos()
            sleep(0.5)
            self.fix_bench_state()
            none_slot = arena_functions.empty_slot()
            sleep(0.5)
            if none_slot != -1:
                print(f"Purchased {champion[1]}")
                if champion[1] in self.champs_to_buy:
                    self.champs_to_buy[champion[1]] -= quantity

    def buy_xp_round(self) -> None:
        """Buy XP if gold is equal to or over 4"""
        if arena_functions.get_gold() >= 4:
            mk_functions.buy_xp()

    def load_aguments(self):
        """Augments from lolchess.gg"""
        return self.comps_manager.current_comp()[2]

    def pick_augment(self) -> None:
        """Picks an augment based on a comp-specific/user-defined augment list
        or defaults to the first augment that is not in the AVOID list"""
        while True:
            sleep(1)
            augments: list = []
            comp_augments = self.load_aguments()
            for coords in screen_coords.AUGMENT_POS:
                augment: str = ocr.get_text(
                    screenxy=coords.get_coords(), scale=3, psm=7
                )
                augments.append(augment)
            print(f"  Augments: {augments}")
            if len(augments) == 3 and "" not in augments:
                break

        for potential in comp_augments + game_assets.AUGMENTS:
            for augment in augments:
                if potential in augment:
                    print(f"  Choosing augment: {augment}")
                    mk_functions.left_click(
                        screen_coords.AUGMENT_LOC[augments.index(augment)].get_coords()
                    )
                    return

        if self.augment_roll:
            print("  Rolling for augment")
            for i in range(0, 3):
                mk_functions.left_click(screen_coords.AUGMENT_ROLL[i].get_coords())
            self.augment_roll = False
            self.pick_augment()
            return

        print(
            "  [!] No priority or backup augment found, undefined behavior may occur for the rest of the round"
        )

        for augment in augments:
            found = False
            for potential in game_assets.AVOID_AUGMENTS:
                if potential in augment:
                    found = True
                    break
                if not found:
                    mk_functions.left_click(
                        screen_coords.AUGMENT_LOC[augments.index(augment)].get_coords()
                    )
                    return
            mk_functions.left_click(screen_coords.AUGMENT_LOC[0].get_coords())

    def can_give_champ_a_completed_secondary_item(self, unit: Champion):
        return unit.item_slots_filled < 5 and (
            arena_functions.get_health() <= 50
            or len([item for item in self.items if item is not None]) == 10
        )

    def check_health(self) -> int:
        """Check the current health and activate spam roll if health is 30 or below"""
        health: int = arena_functions.get_health()
        if health > 0:
            print(f"  Health: {health}")
            if not self.spam_roll and health <= 30:
                print("    Health under 30, spam roll activated")
                self.spam_roll = True
        else:
            print("  Health check failed")
        return health

    def get_label(self) -> None:
        """Gets labels used to display champion name UI on window"""
        labels = [
            (f"{slot.name}", slot.coords)
            for slot in self.bench
            if isinstance(slot, Champion)
        ]

        for slot in self.board:
            if isinstance(slot, Champion):
                labels.append((f"{slot.name}", slot.coords))

        labels.extend(
            (slot, screen_coords.BOARD_LOC[self.unknown_slots[index]].get_coords())
            for index, slot in enumerate(self.board_unknown)
        )
        self.message_queue.put(("LABEL", labels))
