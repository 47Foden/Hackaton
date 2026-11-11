import type { ServiceType } from './api/contracts';
import { useState } from 'react';
import { StartScreen } from './screens/StartScreen';
import { VoiceOrderScreen } from './screens/VoiceOrderScreen';
import { OrderScreen } from './screens/OrderScreen';
import { KioskHistory, useKioskNavigation } from './hooks/useKioskHistory';

export function App() {
  const [serviceType, setServiceType] = useState<ServiceType>('DINE_IN');
  return <KioskHistory>{(screen, session) => <Screens key={session} screen={screen}
    serviceType={serviceType} onServiceType={setServiceType} />}</KioskHistory>;
}

function Screens({ screen, serviceType, onServiceType }: { screen: 'start' | 'order' | 'voice';
  serviceType: ServiceType; onServiceType: (value: ServiceType) => void }) {
  const navigation = useKioskNavigation();
  // The order screen is mounted only for the lifetime of one order session.
  return screen === 'start'
    ? <StartScreen serviceType={serviceType} onServiceType={onServiceType} onStart={() => navigation.navigate('order')} onVoice={() => navigation.navigate('voice')} />
    : screen === 'voice' ? <VoiceOrderScreen serviceType={serviceType} onHome={navigation.home} /> : <OrderScreen serviceType={serviceType} onHome={navigation.home} />;
}
