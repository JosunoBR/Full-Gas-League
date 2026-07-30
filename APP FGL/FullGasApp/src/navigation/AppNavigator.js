import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text, View, StyleSheet, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import Home from '../screens/Home';
import RacesScreen from '../screens/RacesScreen';
import TribunalScreen from '../screens/TribunalScreen';
import StandingsScreen from '../screens/StandingsScreen';
import ProfileScreen from '../screens/ProfileScreen';

const Tab = createBottomTabNavigator();

function TabIcon({ emoji, focused, label }) {
  return (
    <View style={styles.iconContainer}>
      <Text style={[styles.iconEmoji, focused && styles.iconEmojiActive]}>{emoji}</Text>
      <Text style={[styles.iconLabel, focused && styles.iconLabelActive]} numberOfLines={1}>{label}</Text>
    </View>
  );
}

export default function AppNavigator() {
  const insets = useSafeAreaInsets();
  const bottomInset = insets.bottom > 0 ? insets.bottom : (Platform.OS === 'android' ? 10 : 5);

  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,
        tabBarStyle: [
          styles.tabBar,
          {
            height: 60 + bottomInset,
            paddingBottom: bottomInset,
            paddingTop: 6,
          }
        ],
      }}
    >
      <Tab.Screen
        name="HomeTab"
        component={Home}
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon emoji="🏠" focused={focused} label="Cockpit" />
          ),
        }}
      />
      <Tab.Screen
        name="RacesTab"
        component={RacesScreen}
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon emoji="🏁" focused={focused} label="Corridas" />
          ),
        }}
      />
      <Tab.Screen
        name="TribunalTab"
        component={TribunalScreen}
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon emoji="⚖️" focused={focused} label="Tribunal" />
          ),
        }}
      />
      <Tab.Screen
        name="StandingsTab"
        component={StandingsScreen}
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon emoji="🏆" focused={focused} label="Tabela" />
          ),
        }}
      />
      <Tab.Screen
        name="ProfileTab"
        component={ProfileScreen}
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon emoji="👤" focused={focused} label="Perfil" />
          ),
        }}
      />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: '#111728',
    borderTopWidth: 1,
    borderTopColor: '#2a365c',
    height: 65,
    paddingBottom: 5,
    paddingTop: 5,
  },
  iconContainer: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconEmoji: {
    fontSize: 20,
    opacity: 0.6,
  },
  iconEmojiActive: {
    opacity: 1,
    transform: [{ scale: 1.15 }],
  },
  iconLabel: {
    fontSize: 10,
    color: '#888',
    marginTop: 2,
  },
  iconLabelActive: {
    color: '#E60000',
    fontWeight: 'bold',
  },
});
