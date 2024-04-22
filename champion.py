"""
Contains all information related to an individual board slot used by the bot
"""
import arena_functions
import screen_coords
from comps import CompsManager


class Champion:
    """Champion class that contains information about a single unit on the board or bench"""

    # pylint: disable=too-many-instance-attributes,too-few-public-methods,too-many-arguments

    def __init__(
        self,
        name: str,
        coords: tuple,
        build: list[str],
        build2: list[str],
        item_slots_filled: int,
        slot: int,
        size: int,
        final_comp: bool,
        trait1: str,
        trait2: str,
        trait3: str
    ) -> None:
        # The champs name.
        self.name: str = name
        # Where the champ is located on the bench or board in Vec2 coordinates.
        self.coords: tuple = coords
        # A list of items that are likely the champ's best items it can be given for the comp.
        self.build = build
        # A list of recommended items for the champ
        self.secondary_items: list[str] = build2
        # How many item slots are taken up by the champ. There are only 3 item slots, which get translated to 6 slots:
        # completed/non-component items fill up two slots and component items fill up 1.
        self.item_slots_filled: int = item_slots_filled
        # The position on the board where the champ is designated in comp to be placed.
        self.index: int = slot
        # The 'amount of champs' this champ counts as,
        # because sometimes a champ counts as 2 of your total possible champs.
        self.size: int = size
        # The list of every item the champ has.
        self.items: list = []
        # The list of non-component items the champ has.
        self.non_component_items: list = []
        # The champ can only hold one component item at a time.
        self.component_item: str = ""
        # A list that should only be a tuple of (completed_item, component_item), where the component item in the tuple
        # combines with another component item the champ is currently holding to create the completed item.
        # TODO: this shouldn't be a list. might not even be needed
        self.current_building: list = []
        # List of champ traits
        self.traits = [trait1, trait2, trait3]
        # Whether the champ is a part of the final comp.
        self.final_comp: bool = final_comp

    def print_all_class_variables(self):
        """Prints out all of a champ's information."""
        print(f"\t\tChampion Object: {self}")
        print(f"\t\tChampion Name: {self.name}")
        print(f"\t\tLocation in Coordinates: {self.coords}")
        print(f"\t\tItems The Champ is Designated to Build: {self.build}")
        print(f"\t\tLocation Designated in the Comp: {self.index}")
        print(f"\t\tAmount of Spaces This Champ Takes Up on the Board: {self.size}")
        print(f"\t\tCompleted Items: {self.non_component_items}")
        print(f"\t\tComponent Items: {self.current_building}")
        print(f"\t\tFinal Comp? {self.final_comp}")

    def does_need_items(self) -> bool:
        """Returns if the champion instance needs items"""
        return len(self.non_component_items) != 3 or len(self.build) + len(self.current_building) == 0

    def check_trait(self, trait_item: str) -> bool:
        """Check if the champion has a specific trait based on the item passed."""
        # Remove "Emblem" from the item name
        trait_to_check = trait_item.replace("Emblem", "")

        # Check if the trait exists in the champion's traits
        return trait_to_check in self.traits

def create_default_champion( champ_name: str, index: int | None, bench: bool, comps_manager: CompsManager,
                            trait1: str, trait2: str, trait3: str,item_count: int = 0) -> Champion:
    """Creates a default Champion object with given parameters."""
    # Set default values if we don't want to use this champ in our comp.
    if index is None:
        raise ValueError("Index must be provided when bench is True or False")

    # Determine the location of the champion based on if they are on the bench or board.
    coords = screen_coords.BENCH_LOC[index].get_coords() if bench else screen_coords.BOARD_LOC[index].get_coords()

    # Extract current composition and set default values for champion properties.
    current_comp = comps_manager.current_comp()[1]
    build, build2, board_position = [], [], None
    size, final_comp = 1, False

    # Check if the champion is part of the current composition and update properties accordingly.
    if champ_name in current_comp:
        champ_data = current_comp[champ_name]
        champs_current_item_count = arena_functions.count_number_of_item_slots_filled_on_unit_at_coords(coords)
    # If we actually plan on using this champ in our comp:
        build = champ_data.get("items")
        build2 = champ_data.get("recommendItems")
        board_position = champ_data.get("board_position")
        size = comps_manager.champions[champ_name].get("Board Size")
        final_comp = champ_data.get("final_comp")
        trait1 = comps_manager.champions[champ_name].get("Trait1")
        trait2 = comps_manager.champions[champ_name].get("Trait2")
        trait3 = comps_manager.champions[champ_name].get("Trait3")
    else:
        champs_current_item_count = item_count
    # Create the Champion object.

    print(
        f"  Creating Champion -" 
        f"\n    Name: {champ_name}, Build: {build}, Recommended Items: {build2},"
        f"\n    Position: {board_position}, Board Size: {size}, Final Comp: {final_comp}, Traits: {trait1}, {trait2}, {trait3}"
    )

    return Champion(
        name=champ_name, coords=coords, item_slots_filled=champs_current_item_count,
        build=build, build2=build2, slot=board_position, size=size, final_comp=final_comp,
        trait1=trait1, trait2=trait2, trait3=trait3
    )
