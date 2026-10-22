package com.example.game.feature.demo;

import java.util.List;
import com.example.game.shared.Money;
import com.example.game.feature.Features;
import com.example.game.feature.demo.model.DemoState;
import com.example.game.feature.inventory.api.InventoryApi;
import com.example.game.feature.inventory.InventoryService; // EXPECT: MOD-01
import static com.example.game.feature.inventory.InventoryRules.MAX_SLOTS; // EXPECT: MOD-01
import com.example.game.feature.quest.*; // EXPECT: MOD-01
// import com.example.game.feature.quest.QuestLog;

final class CrossFeatureImport {
    List<Money> prices(DemoState state, InventoryApi inventory) {
        return List.of();
    }
}
