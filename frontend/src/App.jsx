import { useAdMakerState } from './state/useAdMakerState.js';
import AppShell from './components/AppShell.jsx';
import Home from './screens/Home.jsx';
import Store from './screens/Store.jsx';
import Character from './screens/Character.jsx';
import CharacterInfo from './screens/CharacterInfo.jsx';
import Ad from './screens/Ad.jsx';
import Trend from './screens/Trend.jsx';
import Storyboard from './screens/Storyboard.jsx';
import Result from './screens/Result.jsx';
import Save from './screens/Save.jsx';
import MyShell from './screens/My/MyShell.jsx';
import MyStore from './screens/MyStore.jsx';

const SCREENS = {
  home: Home,
  store: Store,
  char: Character,
  charInfo: CharacterInfo,
  ad: Ad,
  trend: Trend,
  sb: Storyboard,
  result: Result,
  save: Save,
  my: MyShell,
  myStore: MyStore
};

export default function App() {
  const { state, actions, charLocked, adLocked } = useAdMakerState();
  const Screen = SCREENS[state.screen] || Home;
  const missingProdsCount = state.prods.filter(p => !p.soldOut).length;

  return (
    <AppShell state={state} actions={actions} missingProdsCount={missingProdsCount}>
      <Screen state={state} actions={actions} charLocked={charLocked} adLocked={adLocked} />
    </AppShell>
  );
}
